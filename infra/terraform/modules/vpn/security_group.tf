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

# --- Ingress: OpenVPN (UDP 1194) from allowlisted CIDRs ---

resource "aws_security_group_rule" "vpn_ingress" {
  type              = "ingress"
  from_port         = 1194
  to_port           = 1194
  protocol          = "udp"
  cidr_blocks       = var.allowed_vpn_cidrs
  security_group_id = aws_security_group.vpn.id
  description       = "OpenVPN client connections from allowlisted CIDRs"
}

# --- Egress: allow all outbound (route VPN client traffic to VPC + internet) ---

resource "aws_security_group_rule" "vpn_egress" {
  type              = "egress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.vpn.id
  description       = "Allow all outbound traffic (VPN routing + system updates)"
}
