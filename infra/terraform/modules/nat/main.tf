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

resource "aws_iam_role" "nat_instance" {
  name = "Training-${var.project_name}-${var.env}-nat-instance-role"

  count = var.enabled ? 1 : 0

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
    }]
  })

  tags = merge(var.tags, {
    Name = "Training-${var.project_name}-${var.env}-nat-instance-role"
  })
}

# SSM Session Manager — reach the NAT instance without opening port 22
resource "aws_iam_role_policy_attachment" "nat_instance_ssm" {
  count      = var.enabled && var.enable_ssm ? 1 : 0
  role       = aws_iam_role.nat_instance[0].name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

# CloudWatch Agent — enhanced monitoring for NAT throughput/errors
resource "aws_iam_role_policy_attachment" "nat_instance_cloudwatch" {
  count      = var.enabled && var.enable_cloudwatch ? 1 : 0
  role       = aws_iam_role.nat_instance[0].name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
}

resource "aws_iam_instance_profile" "nat_instance" {
  count = var.enabled ? 1 : 0
  name  = "Training-${var.project_name}-${var.env}-nat-instance-profile"
  role  = aws_iam_role.nat_instance[0].name
}

# Note: EIP will be created by the ec2 module when create_eip = true
module "ec2" {
  source = "../ec2-instance"
  count  = var.enabled ? 1 : 0

  name                        = "${var.project_name}-${var.env}-nat-instance"
  ami                         = data.aws_ami.nat_instance.id
  instance_type               = var.instance_type
  subnet_id                   = var.public_subnet_id
  vpc_security_group_ids      = [module.security_group[0].sg_id]
  iam_instance_profile        = aws_iam_instance_profile.nat_instance[0].name
  key_name                    = var.key_name
  associate_public_ip_address = true
  source_dest_check           = false
  metadata_hop_limit          = 1

  tags = var.tags

  extra_tags = {
    Role = "NAT"
  }

  create_eip = true
}

# --- State Migration ---
moved {
  from = aws_instance.nat_instance[0]
  to   = module.ec2[0].aws_instance.this
}

moved {
  from = aws_eip.nat_instance[0]
  to   = module.ec2[0].aws_eip.this[0]
}

moved {
  from = aws_eip_association.nat_instance[0]
  to   = module.ec2[0].aws_eip_association.this[0]
}

resource "aws_route" "private_nat_instance" {
  count                  = var.enabled ? 1 : 0
  route_table_id         = var.private_route_table_id
  destination_cidr_block = "0.0.0.0/0"
  network_interface_id   = module.ec2[0].primary_network_interface_id
  depends_on             = [module.ec2]
}
