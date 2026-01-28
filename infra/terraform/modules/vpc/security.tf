# ------------------------------------------------------------------------------
# APPLICATION LAYER SECURITY
# ------------------------------------------------------------------------------

# Security group for compute resources (Go and Python services)
resource "aws_security_group" "app" {
  name        = "${var.project_name}-${var.env}-sg-app"
  description = "Security group for application servers (Go/Python)"
  vpc_id      = aws_vpc.main.id

  tags = {
    Name = "${var.project_name}-${var.env}-sg-app"
  }
}

# Outbound rule to allow all traffic. 
# Essential for Long Polling (Telegram API) and system package updates.
resource "aws_security_group_rule" "app_egress_all" {
  type              = "egress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.app.id
  description       = "Allow all outbound traffic for Long Polling and system updates"
}

# ------------------------------------------------------------------------------
# DATABASE LAYER SECURITY
# ------------------------------------------------------------------------------

# Security group for persistent data stores (RDS PostgreSQL)
resource "aws_security_group" "db" {
  name        = "${var.project_name}-${var.env}-sg-db"
  description = "Security group for RDS PostgreSQL"
  vpc_id      = aws_vpc.main.id

  tags = {
    Name = "${var.project_name}-${var.env}-sg-db"
  }
}

# Inbound rule to allow PostgreSQL traffic.
# Implements the principle of least privilege: only the app layer can connect.
resource "aws_security_group_rule" "db_ingress_postgres" {
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.app.id
  security_group_id        = aws_security_group.db.id
  description              = "Only allow PostgreSQL traffic from the app layer security group"
}
