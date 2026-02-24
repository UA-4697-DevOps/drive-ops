# ==============================================================================
# BASTION HOST – SECURITY GROUP
# ==============================================================================
# Strict source-IP allowlist: only IPs in allowed_ssh_cidrs can reach port 22.
# All outbound traffic is allowed so the bastion can reach private-subnet
# resources (EKS API, RDS, etc.) and download OS updates.
# ==============================================================================

resource "aws_security_group" "bastion" {
  name        = "${var.project_name}-${var.env}-bastion-sg"
  description = "Bastion host - strict source-IP allowlist for SSH"
  vpc_id      = var.vpc_id

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.env}-bastion-sg"
  })
}

# --- Ingress: SSH from allowlisted CIDRs only ---

resource "aws_security_group_rule" "ssh_ingress" {
  type              = "ingress"
  from_port         = 22
  to_port           = 22
  protocol          = "tcp"
  cidr_blocks       = var.allowed_ssh_cidrs
  security_group_id = aws_security_group.bastion.id
  description       = "SSH from allowlisted CIDRs"
}

# --- Ingress: OpenVPN (UDP 1194) from allowlisted CIDRs only ---

resource "aws_security_group_rule" "openvpn_ingress" {
  count             = var.enable_openvpn ? 1 : 0
  type              = "ingress"
  from_port         = 1194
  to_port           = 1194
  protocol          = "udp"
  cidr_blocks       = var.allowed_ssh_cidrs
  security_group_id = aws_security_group.bastion.id
  description       = "OpenVPN from allowlisted CIDRs"
}

# --- Egress: all outbound ---

resource "aws_security_group_rule" "all_egress" {
  type              = "egress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = ["0.0.0.0/0"]
  ipv6_cidr_blocks  = ["::/0"]
  security_group_id = aws_security_group.bastion.id
  description       = "All outbound traffic (IPv4 and IPv6)"
}
