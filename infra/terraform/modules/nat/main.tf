# ==============================================================================
# NAT INSTANCE MODULE
# ==============================================================================
# Deploys a NAT Instance using the fck-nat community AMI (ARM64/Graviton).
# Disabled by default (enabled = false) — set enabled = true to provision.
#
# Resources managed:
#   - IAM Role + Instance Profile (SSM Session Manager + CloudWatch access)
#   - Security Group (private-subnet ingress + optional SSH from bastion)
#   - Elastic IP (stable public outbound address)
#   - EC2 Instance (fck-nat AMI, source_dest_check=false for forwarding)
#   - EIP Association
#   - Route: private subnets → NAT instance (0.0.0.0/0)
#
# References:
#   https://github.com/AndrewGuenther/fck-nat
# ==============================================================================

# fck-nat: Community-maintained, production-ready NAT AMI (ARM64/Graviton only)
data "aws_ami" "nat_instance" {
  most_recent = true
  owners      = ["568608671756"] # fck-nat official AWS account

  filter {
    name   = "name"
    values = ["fck-nat-al2023-*-arm64-*"]
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

module "iam_role" {
  source = "../iam-role"
  count  = var.enabled ? 1 : 0

  role_name               = "Training-${var.project_name}-${var.env}-nat-instance-role"
  create_instance_profile = true
  permissions_boundary    = "arn:aws:iam::${var.account_id}:policy/DevOpsBound"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
    }]
  })

  managed_policy_arns = compact([
    var.enable_ssm ? "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore" : "",
    var.enable_cloudwatch ? "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy" : ""
  ])

  tags = { Name = "Training-${var.project_name}-${var.env}-nat-instance-role" }
}

# ==============================================================================
# Security Group
# ==============================================================================

resource "aws_security_group" "nat_instance" {
  count       = var.enabled ? 1 : 0
  name        = "${var.project_name}-${var.env}-nat-instance-sg"
  description = "NAT Instance — allows forwarding traffic from private subnets to internet"
  vpc_id      = var.vpc_id

  # Allow all inbound from private subnets (NAT forwarding)
  ingress {
    description = "NAT forwarding from private subnets"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = var.private_subnet_cidrs
  }

  # Optional: SSH break-glass access from bastion/VPN
  dynamic "ingress" {
    for_each = length(var.allowed_ssh_cidrs) > 0 ? [1] : []
    content {
      description = "SSH break-glass from bastion or VPN"
      from_port   = 22
      to_port     = 22
      protocol    = "tcp"
      cidr_blocks = var.allowed_ssh_cidrs
    }
  }

  # Full outbound to internet (required for NAT)
  egress {
    description = "Outbound to internet"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.project_name}-${var.env}-nat-instance-sg" }
}

# ==============================================================================
# Elastic IP
# ==============================================================================

resource "aws_eip" "nat_instance" {
  count  = var.enabled ? 1 : 0
  domain = "vpc"
  tags   = { Name = "${var.project_name}-${var.env}-nat-instance-eip" }
}

# ==============================================================================
# EC2 Instance (fck-nat — pre-configured AMI, no user_data needed)
# ==============================================================================

resource "aws_instance" "nat_instance" {
  count                       = var.enabled ? 1 : 0
  ami                         = data.aws_ami.nat_instance.id
  instance_type               = var.instance_type
  subnet_id                   = var.public_subnet_id
  vpc_security_group_ids      = [aws_security_group.nat_instance[0].id]
  iam_instance_profile        = module.iam_role[0].iam_instance_profile_name
  key_name                    = var.key_name
  associate_public_ip_address = true

  # CRITICAL: Disables source/destination check so the instance can forward
  # traffic that is not destined for itself (i.e., act as a router/NAT).
  source_dest_check = false

  # fck-nat AMI ships pre-configured with:
  #   - IP forwarding (net.ipv4.ip_forward = 1)
  #   - iptables MASQUERADE rules for outbound NAT
  #   - Auto-recovery scripts
  #   - CloudWatch monitoring integration
  # No user_data script is required.

  # IMDSv2 — prevents SSRF-based credential theft
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
    instance_metadata_tags      = "enabled"
  }

  root_block_device {
    volume_type           = "gp3"
    volume_size           = 8
    encrypted             = true
    delete_on_termination = true
  }

  tags = {
    Name = "${var.project_name}-${var.env}-nat-instance"
    Role = "NAT"
  }

  # Prevent forced replacement when fck-nat publishes a new AMI version.
  # Update explicitly: terraform apply -replace=aws_instance.nat_instance
  lifecycle {
    ignore_changes = [ami]
  }
}

# ==============================================================================
# EIP Association
# ==============================================================================

resource "aws_eip_association" "nat_instance" {
  count         = var.enabled ? 1 : 0
  instance_id   = aws_instance.nat_instance[0].id
  allocation_id = aws_eip.nat_instance[0].id
}

# ==============================================================================
# Private Route: 0.0.0.0/0 → NAT Instance
# ==============================================================================
# This route enables outbound internet access for resources in private subnets
# (e.g., EKS worker nodes pulling images, RDS patch downloads).

resource "aws_route" "private_nat_instance" {
  count                  = var.enabled ? 1 : 0
  route_table_id         = var.private_route_table_id
  destination_cidr_block = "0.0.0.0/0"
  network_interface_id   = aws_instance.nat_instance[0].primary_network_interface_id
  depends_on             = [aws_instance.nat_instance]
}




#-------------------
moved {
  from = aws_iam_role.nat_instance[0]
  to   = module.iam_role[0].aws_iam_role.this
}

moved {
  from = aws_iam_instance_profile.nat_instance[0]
  to   = module.iam_role[0].aws_iam_instance_profile.this[0]
}

moved {
  from = aws_iam_role_policy_attachment.nat_instance_ssm[0]
  to   = module.iam_role[0].aws_iam_role_policy_attachment.managed_attach["arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"]
}

moved {
  from = aws_iam_role_policy_attachment.nat_instance_cloudwatch[0]
  to   = module.iam_role[0].aws_iam_role_policy_attachment.managed_attach["arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"]
}