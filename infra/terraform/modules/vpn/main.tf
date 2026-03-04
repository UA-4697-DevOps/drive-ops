# ==============================================================================
# VPN MODULE (OpenVPN)
# ==============================================================================
# Deploys a standalone OpenVPN server on a dedicated EC2 instance, separate from
# the SSH bastion host. This provides a secure VPN gateway for administrative
# access to private VPC resources (EKS worker nodes, RDS, etc.) without exposing
# individual services directly.
#
# Resources:
#   - IAM Role + Instance Profile (SSM + Secrets Manager for PKI persistence)
#   - Security Group (UDP 1194 from allowlisted CIDRs)
#   - Elastic IP (stable public endpoint interpolated into .ovpn client config)
#   - EC2 Instance (AL2023 ARM64 — OpenVPN + EasyRSA configured via user_data)
#
# PKI Durability:
#   The CA, server cert, client certs and Diffie-Hellman params are generated on
#   first boot and persisted to Secrets Manager. On every subsequent boot (or
#   after instance replacement) they are restored from Secrets Manager so that
#   existing client .ovpn profiles remain valid indefinitely.
#
# Retrieve client config:
#   aws secretsmanager get-secret-value \
#     --secret-id "<project>/<env>/openvpn/clients/client1" \
#     --query SecretString --output text > client1.ovpn
# ==============================================================================

# ==============================================================================
# Variables
# ==============================================================================

variable "ami_id" {
  type        = string
  default     = null
  description = "Optional AMI ID for the VPN instance. If not provided, the latest Amazon Linux 2023 ARM64 AMI will be used."
  validation {
    condition     = var.ami_id == null || trimspace(var.ami_id) != ""
    error_message = "ami_id, when provided, must be a non-empty AMI ID."
  }
}

# --- Validation ---

resource "null_resource" "validate_vpn_cidr" {
  lifecycle {
    precondition {
      condition     = var.vpc_cidr != "" && can(cidrhost(var.vpc_cidr, 0))
      error_message = "vpc_cidr must be a valid CIDR block. OpenVPN pushes this route to clients so they can reach private subnets."
    }
    precondition {
      condition     = var.vpn_client_cidr != "" && can(cidrhost(var.vpn_client_cidr, 0))
      error_message = "vpn_client_cidr must be a valid CIDR block so OpenVPN can assign client tunnel addresses."
    }
  }
}

# --- Latest Amazon Linux 2023 AMI (ARM64 / Graviton) ---

data "aws_ami" "al2023" {
  count       = var.ami_id == null ? 1 : 0
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-arm64"]
  }

  filter {
    name   = "architecture"
    values = ["arm64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# ==============================================================================
# IAM Role & Instance Profile
# ==============================================================================

data "aws_iam_policy_document" "vpn_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "vpn" {
  name                 = "Training-${var.project_name}-${var.env}-vpn-role"
  assume_role_policy   = data.aws_iam_policy_document.vpn_assume_role.json
  permissions_boundary = "arn:aws:iam::${var.account_id}:policy/DevOpsBound"

  tags = merge(var.tags, {
    Name = "Training-${var.project_name}-${var.env}-vpn-role"
  })
}

# SSM Session Manager — administrative access without opening port 22
resource "aws_iam_role_policy_attachment" "vpn_ssm" {
  role       = aws_iam_role.vpn.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

# Least-privilege Secrets Manager — only OpenVPN PKI secrets for this project/env
resource "aws_iam_role_policy" "vpn_secrets" {
  name = "${var.project_name}-${var.env}-vpn-secrets-policy"
  role = aws_iam_role.vpn.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(
      [
        {
          Effect = "Allow"
          Action = [
            "secretsmanager:CreateSecret",
            "secretsmanager:DescribeSecret",
            "secretsmanager:GetSecretValue",
            "secretsmanager:PutSecretValue",
          ]
          Resource = "arn:aws:secretsmanager:${var.aws_region}:${var.account_id}:secret:${var.project_name}/${var.env}/openvpn/*"
        },
      ],
      var.kms_key_arn != null ? [
        {
          Effect = "Allow"
          Action = [
            "kms:Decrypt",
            "kms:DescribeKey",
            "kms:GenerateDataKey",
          ]
          Resource = var.kms_key_arn
        },
      ] : []
    )
  })
}

resource "aws_iam_instance_profile" "vpn" {
  name = "Training-${var.project_name}-${var.env}-vpn-profile"
  role = aws_iam_role.vpn.name

  tags = merge(var.tags, {
    Name = "Training-${var.project_name}-${var.env}-vpn-profile"
  })
}

# ==============================================================================
# Elastic IP — allocated first so the public IP can be embedded in user_data
# ==============================================================================

resource "aws_eip" "vpn" {
  domain = "vpc"

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.env}-vpn-eip"
  })
}

# ==============================================================================
# EC2 Instance
# ==============================================================================

resource "aws_instance" "vpn" {
  ami                    = var.ami_id != null ? var.ami_id : data.aws_ami.al2023[0].id
  instance_type          = var.instance_type
  subnet_id              = var.public_subnet_id
  vpc_security_group_ids = [aws_security_group.vpn.id]
  key_name               = var.key_name
  iam_instance_profile   = aws_iam_instance_profile.vpn.name
  monitoring             = true
  source_dest_check      = false # Required: allows the instance to forward VPN client traffic

  user_data = templatefile("${path.module}/scripts/user-data.sh.tpl", {
    project_name    = var.project_name
    env             = var.env
    aws_region      = var.aws_region
    kms_key_arn     = var.kms_key_arn
    vpn_client_cidr = var.vpn_client_cidr
    vpc_cidr        = var.vpc_cidr
    eip_public_ip   = aws_eip.vpn.public_ip
  })

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required" # IMDSv2 only
    http_put_response_hop_limit = 1
  }

  root_block_device {
    volume_type           = "gp3"
    volume_size           = 8
    encrypted             = true
    delete_on_termination = true
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.env}-vpn"
    Role = "VPN"
  })

  lifecycle {
    # user_data changes require explicit replacement to avoid PKI regeneration
    ignore_changes = [user_data]
  }
}

# ==============================================================================
# EIP Association
# ==============================================================================

resource "aws_eip_association" "vpn" {
  instance_id   = aws_instance.vpn.id
  allocation_id = aws_eip.vpn.id
}
