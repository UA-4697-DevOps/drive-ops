# ==============================================================================
# COMPUTE – SECURITY GROUP
# ==============================================================================

module "security_group" {
  source = "../security-group"

  name        = "${var.name}-ec2-sg"
  description = "Security group for ${var.name} EC2 instance"
  vpc_id      = var.vpc_id

  ingress_rules = concat(
    length(var.allowed_ssh_cidr_blocks) > 0 ? [{
      key         = "ssh_ingress"
      from_port   = 22
      to_port     = 22
      protocol    = "tcp"
      cidr_blocks = var.allowed_ssh_cidr_blocks
      description = "Allow SSH access"
    }] : [],
    length(var.allowed_http_cidr_blocks) > 0 ? [{
      key         = "http_ingress"
      from_port   = 80
      to_port     = 80
      protocol    = "tcp"
      cidr_blocks = var.allowed_http_cidr_blocks
      description = "Allow HTTP access"
    }] : [],
    length(var.allowed_https_cidr_blocks) > 0 ? [{
      key         = "https_ingress"
      from_port   = 443
      to_port     = 443
      protocol    = "tcp"
      cidr_blocks = var.allowed_https_cidr_blocks
      description = "Allow HTTPS access"
    }] : [],
    var.app_port > 0 ? [{
      key         = "app_port_ingress"
      from_port   = var.app_port
      to_port     = var.app_port
      protocol    = "tcp"
      cidr_blocks = var.allowed_app_port_cidr_blocks
      description = "Allow application traffic on port ${var.app_port}"
    }] : []
  )

  egress_rules = [
    {
      key         = "egress_all"
      from_port   = 0
      to_port     = 0
      protocol    = "-1"
      cidr_blocks = ["0.0.0.0/0"]
      description = "Allow all outbound traffic"
    }
  ]

  tags = var.tags
}

moved {
  from = aws_security_group.ec2
  to   = module.security_group.aws_security_group.this
}

moved {
  from = aws_security_group_rule.egress
  to   = module.security_group.aws_security_group_rule.egress["egress_all"]
}

moved {
  from = aws_security_group_rule.ssh_ingress[0]
  to   = module.security_group.aws_security_group_rule.ingress["ssh_ingress"]
}

moved {
  from = aws_security_group_rule.http_ingress[0]
  to   = module.security_group.aws_security_group_rule.ingress["http_ingress"]
}

moved {
  from = aws_security_group_rule.https_ingress[0]
  to   = module.security_group.aws_security_group_rule.ingress["https_ingress"]
}

moved {
  from = aws_security_group_rule.app_port_ingress[0]
  to   = module.security_group.aws_security_group_rule.ingress["app_port_ingress"]
}
