# ------------------------------------------------------------------------------
# APP SECURITY GROUP (Compute Layer)
# ------------------------------------------------------------------------------
resource "aws_security_group" "app" {
  name        = "${var.project_name}-${var.env}-sg-app"
  description = "Security group for application servers (Go/Python)"
  vpc_id      = aws_vpc.main.id

  tags = {
    Name = "${var.project_name}-${var.env}-sg-app"
  }
}

# Rule: Allow HTTPS (443) - Primary Secure Traffic
resource "aws_security_group_rule" "app_ingress_https" {
  type              = "ingress"
  from_port         = 443
  to_port           = 443
  protocol          = "tcp"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.app.id
  description       = "Allow secure HTTPS traffic from the internet (Telegram Webhooks/API)"
}

# Rule: Allow HTTP (80) - Redirection Only
# Note: We allow port 80 solely for Nginx to redirect traffic to 443.
# We do not use an ALB to maintain Free Tier cost efficiency.
resource "aws_security_group_rule" "app_ingress_http_redirect" {
  type              = "ingress"
  from_port         = 80
  to_port           = 80
  protocol          = "tcp"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.app.id
  description       = "Allow HTTP traffic ONLY for redirection to HTTPS"
}

# Rule: Egress (Outbound) - Allow All
resource "aws_security_group_rule" "app_egress_all" {
  type              = "egress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.app.id
  description       = "Allow all outbound traffic for system updates and AWS service calls"
}

# ------------------------------------------------------------------------------
# DB SECURITY GROUP (Data Layer)
# ------------------------------------------------------------------------------
resource "aws_security_group" "db" {
  name        = "${var.project_name}-${var.env}-sg-db"
  description = "Security group for RDS PostgreSQL"
  vpc_id      = aws_vpc.main.id

  tags = {
    Name = "${var.project_name}-${var.env}-sg-db"
  }
}

# Rule: Allow PostgreSQL (5432) - Internal Only
resource "aws_security_group_rule" "db_ingress_postgres" {
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.app.id
  security_group_id        = aws_security_group.db.id
  description              = "Only allow PostgreSQL traffic from the application security group"
}
