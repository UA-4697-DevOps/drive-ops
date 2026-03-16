# ==============================================================================
# BASTION HOST MODULE
# ==============================================================================
# Deploys a hardened SSH jump-host in a public subnet with:
#   - Strict source-IP SSH allowlist (Security Group)
#   - IMDSv2 enforced (prevents SSRF / credential theft)
#   - SSH hardening via user_data (root login disabled, key-only auth)
#   - Elastic IP for a stable public address
#   - Encrypted root volume
#
# VPN access is handled by the standalone modules/vpn/ module.
# ==============================================================================

# --- Latest Amazon Linux 2023 AMI (ARM64 / Graviton) ---

data "aws_ami" "al2023" {
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

# --- IAM Role & Instance Profile ---

data "aws_iam_policy_document" "bastion_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

module "iam_role" {
  source = "../iam-role"

  role_name               = "Training-${var.project_name}-${var.env}-bastion-role"
  assume_role_policy      = data.aws_iam_policy_document.bastion_assume_role.json
  create_instance_profile = true
  permissions_boundary    = "arn:aws:iam::${var.account_id}:policy/DevOpsBound"

  managed_policy_arns = [
    "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
  ]

  tags = merge(var.tags, {
    Name = "Training-${var.project_name}-${var.env}-bastion-role"
  })
}

# --- Elastic IP (allocated first so it can be referenced in outputs) ---

resource "aws_eip" "bastion" {
  domain = "vpc"

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.env}-bastion-eip"
  })
}

# --- EC2 Instance ---

resource "aws_instance" "bastion" {
  ami                    = data.aws_ami.al2023.id
  instance_type          = var.instance_type
  subnet_id              = var.public_subnet_id
  vpc_security_group_ids = [aws_security_group.bastion.id]
  key_name               = var.key_name
  iam_instance_profile   = module.iam_role.iam_instance_profile_name
  monitoring             = true

  user_data = file("${path.module}/scripts/user-data.sh")

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required" # IMDSv2 only
    http_put_response_hop_limit = 1
  }

  root_block_device {
    volume_size = 20
    volume_type = "gp3"
    encrypted   = true
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.env}-bastion"
  })

  depends_on = [
    module.iam_role
  ]

  lifecycle {
    ignore_changes = [ami]
  }
}

# --- Associate EIP with Instance ---

resource "aws_eip_association" "bastion" {
  instance_id   = aws_instance.bastion.id
  allocation_id = aws_eip.bastion.id
}
