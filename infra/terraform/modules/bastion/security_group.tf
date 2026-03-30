module "security_group" {
  source = "../security-group"

  name        = "${var.project_name}-${var.env}-bastion-sg"
  description = "Bastion host - strict source-IP allowlist for SSH"
  vpc_id      = var.vpc_id

  ingress_rules = [
    {
      key         = "ssh_ingress"
      from_port   = 22
      to_port     = 22
      protocol    = "tcp"
      cidr_blocks = var.allowed_ssh_cidrs
      description = "SSH from allowlisted CIDRs"
    }
  ]

  egress_rules = [
    {
      key         = "egress_vpc_all"
      from_port   = 0
      to_port     = 0
      protocol    = "-1"
      cidr_blocks = [var.vpc_cidr_block]
      description = "All traffic to VPC CIDR (private resources, DNS, etc.)"
    },
    {
      key         = "egress_https"
      from_port   = 443
      to_port     = 443
      protocol    = "tcp"
      cidr_blocks = ["0.0.0.0/0"]
      description = "HTTPS outbound - OS updates and AWS API calls"
    },
    {
      key         = "egress_http"
      from_port   = 80
      to_port     = 80
      protocol    = "tcp"
      cidr_blocks = ["0.0.0.0/0"]
      description = "HTTP outbound - package repository mirrors"
    }
  ]

  tags = var.tags
}

moved {
  from = aws_security_group.bastion
  to   = module.security_group.aws_security_group.this
}

moved {
  from = aws_security_group_rule.ssh_ingress
  to   = module.security_group.aws_security_group_rule.ingress["ssh_ingress"]
}

moved {
  from = aws_security_group_rule.egress_vpc_all
  to   = module.security_group.aws_security_group_rule.egress["egress_vpc_all"]
}

moved {
  from = aws_security_group_rule.egress_https
  to   = module.security_group.aws_security_group_rule.egress["egress_https"]
}

moved {
  from = aws_security_group_rule.egress_http
  to   = module.security_group.aws_security_group_rule.egress["egress_http"]
}
