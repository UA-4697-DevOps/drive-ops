resource "aws_security_group" "app" {
  name   = "${var.project_name}-${var.env}-sg-app"
  vpc_id = aws_vpc.main.id

  # Ingress Rule: HTTPS for secure encrypted traffic
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"] # Required for secure Telegram Webhooks and User API
    description = "Allow secure HTTPS traffic from the internet"
  }

  # Ingress Rule: HTTP for redirection only (Minimal Attack Surface)
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow HTTP only for redirection to HTTPS"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound traffic for updates and AWS service calls"
  }
}

resource "aws_security_group" "db" {
  name   = "${var.project_name}-${var.env}-sg-db"
  vpc_id = aws_vpc.main.id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.app.id] # Only allow access from the app security group
    description     = "Only allow PostgreSQL traffic from the application layer"
  }
}
