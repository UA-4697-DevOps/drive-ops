# ------------------------------------------------------------------------------
# APPLICATION LOAD BALANCER SECURITY
# ------------------------------------------------------------------------------

# Security group for Application Load Balancer
resource "aws_security_group" "alb" {
  name        = "${var.project_name}-${var.env}-sg-alb"
  description = "Security group for Application Load Balancer"
  vpc_id      = aws_vpc.main.id

  tags = {
    Name = "${var.project_name}-${var.env}-sg-alb"
  }
}

# Inbound rule: Allow HTTP traffic from the internet
resource "aws_security_group_rule" "alb_ingress_http" {
  type              = "ingress"
  from_port         = 80
  to_port           = 80
  protocol          = "tcp"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.alb.id
  description       = "Allow HTTP traffic from the internet"
}

# Inbound rule: Allow HTTPS traffic from the internet
resource "aws_security_group_rule" "alb_ingress_https" {
  type              = "ingress"
  from_port         = 443
  to_port           = 443
  protocol          = "tcp"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.alb.id
  description       = "Allow HTTPS traffic from the internet"
}

# Outbound rule: Allow ALB to reach application pods in VPC
resource "aws_security_group_rule" "alb_egress_to_vpc" {
  type              = "egress"
  from_port         = 0
  to_port           = 65535
  protocol          = "tcp"
  cidr_blocks       = [var.vpc_cidr]
  security_group_id = aws_security_group.alb.id
  description       = "Allow ALB to reach application pods in VPC"
}

# Inbound rule: Allow traffic from ALB to application layer
resource "aws_security_group_rule" "app_ingress_from_alb" {
  type                     = "ingress"
  from_port                = 0
  to_port                  = 65535
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.alb.id
  security_group_id        = aws_security_group.app.id
  description              = "Allow traffic from ALB to application pods"
}
