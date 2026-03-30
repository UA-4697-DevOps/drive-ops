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

resource "aws_iam_role" "bastion" {
  name                 = "Training-${var.project_name}-${var.env}-bastion-role"
  assume_role_policy   = data.aws_iam_policy_document.bastion_assume_role.json
  permissions_boundary = "arn:aws:iam::${var.account_id}:policy/DevOpsBound"

  tags = merge(var.tags, {
    Name = "Training-${var.project_name}-${var.env}-bastion-role"
  })
}

# SSM Session Manager — engineers can open a shell without opening port 22
resource "aws_iam_role_policy_attachment" "bastion_ssm" {
  role       = aws_iam_role.bastion.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "bastion" {
  name = "Training-${var.project_name}-${var.env}-bastion-profile"
  role = aws_iam_role.bastion.name

  tags = merge(var.tags, {
    Name = "Training-${var.project_name}-${var.env}-bastion-profile"
  })
}

# --- EC2 Instance + Elastic IP ---

module "ec2" {
  source = "../ec2-instance"

  name                   = "${var.project_name}-${var.env}-bastion"
  ami                    = data.aws_ami.al2023.id
  instance_type          = var.instance_type
  subnet_id              = var.public_subnet_id
  vpc_security_group_ids = [module.security_group.sg_id]
  key_name               = var.key_name
  iam_instance_profile   = aws_iam_instance_profile.bastion.name
  monitoring             = true
  user_data              = file("${path.module}/scripts/user-data.sh")
  metadata_hop_limit     = 1
  create_eip             = true

  tags = var.tags
}

# --- State Migration ---
moved {
  from = aws_instance.bastion
  to   = module.ec2.aws_instance.this
}

moved {
  from = aws_eip.bastion
  to   = module.ec2.aws_eip.this[0]
}

moved {
  from = aws_eip_association.bastion
  to   = module.ec2.aws_eip_association.this[0]
}
