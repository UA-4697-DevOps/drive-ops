module "security_group" {
  source = "../security-group"
  count  = var.enabled ? 1 : 0

  name        = "${var.project_name}-${var.env}-nat-instance-sg"
  description = "NAT Instance - allows forwarding traffic from private subnets to internet"
  vpc_id      = var.vpc_id

  ingress_rules = concat(
    [
      {
        key         = "nat_forwarding"
        from_port   = 0
        to_port     = 0
        protocol    = "-1"
        cidr_blocks = var.private_subnet_cidrs
        description = "NAT forwarding from private subnets"
      }
    ],
    length(var.allowed_ssh_cidrs) > 0 ? [{
      key         = "ssh_breakglass"
      from_port   = 22
      to_port     = 22
      protocol    = "tcp"
      cidr_blocks = var.allowed_ssh_cidrs
      description = "SSH break-glass from bastion or VPN"
    }] : []
  )

  egress_rules = [
    {
      key         = "egress_all"
      from_port   = 0
      to_port     = 0
      protocol    = "-1"
      cidr_blocks = ["0.0.0.0/0"]
      description = "Outbound to internet"
    }
  ]

  tags = var.tags
}

moved {
  from = aws_security_group.nat_instance[0]
  to   = module.security_group[0].aws_security_group.this
}
