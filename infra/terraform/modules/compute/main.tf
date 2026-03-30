module "ec2" {
  source = "../ec2-instance"

  name                        = var.name
  ami                         = local.resolved_ami
  instance_type               = var.instance_type
  subnet_id                   = var.subnet_id
  vpc_security_group_ids      = concat([module.security_group.sg_id], var.additional_security_group_ids)
  key_name                    = var.key_name
  associate_public_ip_address = var.associate_public_ip_address
  iam_instance_profile        = aws_iam_instance_profile.ec2_profile.name
  monitoring                  = var.enable_monitoring
  user_data                   = local.resolved_user_data
  disable_api_termination     = var.enable_termination_protection

  root_volume_size = var.root_volume_size
  root_volume_type = var.root_volume_type

  tags = var.tags
}

# --- State Migration ---
moved {
  from = aws_instance.this
  to   = module.ec2.aws_instance.this
}

resource "aws_security_group_rule" "compute_ingress_internal" {
  type              = "ingress"
  from_port         = 0
  to_port           = 65535
  protocol          = "tcp"
  cidr_blocks       = ["10.0.0.0/16"]
  security_group_id = module.security_group.sg_id
  description       = "Allow all TCP from internal VPC (VPN access)"
}

resource "aws_security_group_rule" "compute_icmp_internal" {
  type              = "ingress"
  from_port         = -1
  to_port           = -1
  protocol          = "icmp"
  cidr_blocks       = ["10.0.0.0/16"]
  security_group_id = module.security_group.sg_id
  description       = "Allow Ping from internal VPC"
}