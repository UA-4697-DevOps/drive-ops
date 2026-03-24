module "security_group" {
  source = "../security-group"

  name        = "${var.project_name}-${var.env}-vpn-sg"
  description = "OpenVPN server — UDP 1194 from allowlisted CIDRs only"
  vpc_id      = var.vpc_id

  ingress_rules = [
    {
      key         = "ingress_vpn"
      from_port   = 1194
      to_port     = 1194
      protocol    = "udp"
      cidr_blocks = var.allowed_vpn_cidrs
      description = "OpenVPN client connections from allowlisted CIDRs"
    }
  ]

  egress_rules = [
    {
      key         = "egress_all"
      from_port   = 0
      to_port     = 0
      protocol    = "-1"
      cidr_blocks = ["0.0.0.0/0"]
      description = "Allow all outbound traffic (VPN routing + system updates)"
    }
  ]

  tags = var.tags
}

moved {
  from = aws_security_group.vpn
  to   = module.security_group.aws_security_group.this
}

moved {
  from = aws_security_group_rule.vpn_rules["ingress_vpn"]
  to   = module.security_group.aws_security_group_rule.ingress["ingress_vpn"]
}

moved {
  from = aws_security_group_rule.vpn_rules["egress_all"]
  to   = module.security_group.aws_security_group_rule.egress["egress_all"]
}
