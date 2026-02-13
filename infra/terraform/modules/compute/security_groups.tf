resource "aws_security_group" "ec2" {
  name        = "${var.name}-ec2-sg"
  description = "Security group for ${var.name} EC2 instance"
  vpc_id      = var.vpc_id

  tags = merge(var.tags, {
    Name = "${var.name}-ec2-sg"
  })
}

resource "aws_security_group_rule" "ssh_ingress" {
  count             = length(var.allowed_ssh_cidr_blocks) > 0 ? 1 : 0
  type              = "ingress"
  from_port         = 22
  to_port           = 22
  protocol          = "tcp"
  security_group_id = aws_security_group.ec2.id
  cidr_blocks       = var.allowed_ssh_cidr_blocks
  description       = "Allow SSH access"
}

resource "aws_security_group_rule" "http_ingress" {
  count             = length(var.allowed_http_cidr_blocks) > 0 ? 1 : 0
  type              = "ingress"
  from_port         = 80
  to_port           = 80
  protocol          = "tcp"
  security_group_id = aws_security_group.ec2.id
  cidr_blocks       = var.allowed_http_cidr_blocks
  description       = "Allow HTTP access"
}

resource "aws_security_group_rule" "https_ingress" {
  count             = length(var.allowed_https_cidr_blocks) > 0 ? 1 : 0
  type              = "ingress"
  from_port         = 443
  to_port           = 443
  protocol          = "tcp"
  security_group_id = aws_security_group.ec2.id
  cidr_blocks       = var.allowed_https_cidr_blocks
  description       = "Allow HTTPS access"
}

resource "aws_security_group_rule" "app_port_ingress" {
  count             = var.app_port > 0 ? 1 : 0
  type              = "ingress"
  from_port         = var.app_port
  to_port           = var.app_port
  protocol          = "tcp"
  security_group_id = aws_security_group.ec2.id
  cidr_blocks       = var.allowed_app_port_cidr_blocks
  description       = "Allow application traffic on port ${var.app_port}"
}

resource "aws_security_group_rule" "egress" {
  type              = "egress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  security_group_id = aws_security_group.ec2.id
  cidr_blocks       = ["0.0.0.0/0"]
  description       = "Allow all outbound traffic"
}
