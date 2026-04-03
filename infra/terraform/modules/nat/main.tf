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
}
resource "aws_eip" "nat_instance" {
  count  = var.enabled ? 1 : 0
  domain = "vpc"

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.env}-nat-instance-eip"
  })
}

resource "aws_instance" "nat_instance" {
  count                       = var.enabled ? 1 : 0
  ami                         = data.aws_ami.nat_instance.id
  instance_type               = var.instance_type
  subnet_id                   = var.public_subnet_id
  vpc_security_group_ids      = [module.security_group[0].sg_id]
  iam_instance_profile        = module.iam_role[0].iam_instance_profile_name
  key_name                    = var.key_name
  associate_public_ip_address = true
  source_dest_check           = false

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
    instance_metadata_tags      = "enabled"
  }

  root_block_device {
    volume_type           = "gp3"
    volume_size           = 30
    encrypted             = true
    delete_on_termination = true
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.env}-nat-instance"
    Role = "NAT"
  })

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