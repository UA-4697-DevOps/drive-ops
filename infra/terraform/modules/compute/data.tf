data "aws_ssm_parameter" "al2023_ami" {
  count = var.ami == null ? 1 : 0
  name  = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

data "aws_region" "current" {}

locals {
  resolved_ami = var.ami != null ? var.ami : data.aws_ssm_parameter.al2023_ami[0].value

  # Construct permissions boundary from account_id (DevOpsBound is required in this account)
  permissions_boundary = var.account_id != null ? "arn:aws:iam::${var.account_id}:policy/DevOpsBound" : null

  # Bootstrap user_data: install Docker and create service directory
  # Overridden by var.user_data if explicitly set
  bootstrap_user_data = <<-EOF
    #!/bin/bash
    set -ex

    # Install Docker
    dnf update -y
    dnf install -y docker
    systemctl enable --now docker
    usermod -aG docker ec2-user

    # Install Docker Compose plugin
    mkdir -p /usr/local/lib/docker/cli-plugins
    curl -fsSL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-$(uname -m)" \
      -o /usr/local/lib/docker/cli-plugins/docker-compose
    chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

    # Create service working directory
    mkdir -p /opt/${var.name}

    echo "Bootstrap complete" | tee -a /var/log/user-data.log
  EOF

  resolved_user_data = var.user_data != null ? var.user_data : local.bootstrap_user_data
}
