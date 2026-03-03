# ==============================================================================
# BASTION HOST – SECURITY GROUP
# ==============================================================================
# Strict source-IP allowlist: only IPs in allowed_ssh_cidrs can reach port 22.
# Egress is scoped to least-privilege:
#   - All traffic to VPC CIDR (private resources, DNS resolver)
#   - HTTPS/HTTP to 0.0.0.0/0 (OS updates, AWS API calls)
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

# --- Egress: least-privilege outbound rules ---

# 1. All traffic to VPC CIDR — covers SSH to private instances, RDS (5432),
#    EKS API (443), DNS resolution via VPC resolver, and any other internal service.
resource "aws_security_group_rule" "egress_vpc_all" {
  type              = "egress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = [var.vpc_cidr_block]
  security_group_id = aws_security_group.bastion.id
  description       = "All traffic to VPC CIDR (private resources, DNS, etc.)"
}

# 2. HTTPS to the internet — OS/package updates (apt, yum, pip) and AWS API calls.
resource "aws_security_group_rule" "egress_https" {
  type              = "egress"
  from_port         = 443
  to_port           = 443
  protocol          = "tcp"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.bastion.id
  description       = "HTTPS outbound — OS updates and AWS API calls"
}

# 3. HTTP to the internet — some package repositories still serve over plain HTTP.
resource "aws_security_group_rule" "egress_http" {
  type              = "egress"
  from_port         = 80
  to_port           = 80
  protocol          = "tcp"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.bastion.id
  description       = "HTTP outbound — package repository mirrors"
}
