# ==============================================================================
# VPN SECURITY GROUP
# ==============================================================================
# Allows OpenVPN clients to connect on UDP 1194 from allowlisted CIDRs only.
# All outbound traffic is permitted so the VPN server can route client traffic
# to private VPC resources and the internet.
# ==============================================================================

resource "aws_security_group" "vpn" {
  name        = "${var.project_name}-${var.env}-vpn-sg"
  description = "OpenVPN server — UDP 1194 from allowlisted CIDRs only"
  vpc_id      = var.vpc_id

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.env}-vpn-sg"
  })
}

# --- Default security group rules ---

locals {
  vpn_rules = {
    ingress_vpn = {
      type        = "ingress"
      from_port   = 1194
      to_port     = 1194
      protocol    = "udp"
      cidr_blocks = var.allowed_vpn_cidrs
      description = "OpenVPN client connections from allowlisted CIDRs"
    }
    egress_all = {
      type        = "egress"
      from_port   = 0
      to_port     = 0
      protocol    = "-1"
      cidr_blocks = ["0.0.0.0/0"]
      description = "Allow all outbound traffic (VPN routing + system updates)"
    }
  }
}

resource "aws_security_group_rule" "vpn_rules" {
  for_each = local.vpn_rules

  type              = each.value.type
  from_port         = each.value.from_port
  to_port           = each.value.to_port
  protocol          = each.value.protocol
  cidr_blocks       = each.value.cidr_blocks
  security_group_id = aws_security_group.vpn.id
  description       = each.value.description
}
