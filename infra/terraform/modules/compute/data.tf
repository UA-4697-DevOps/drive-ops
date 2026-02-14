data "aws_region" "current" {}

locals {
  resolved_ami = var.ami

  # Construct permissions boundary from account_id (DevOpsBound is required in this account)
  permissions_boundary = var.account_id != null ? "arn:aws:iam::${var.account_id}:policy/DevOpsBound" : null

  # Bootstrap user_data: install Docker and create service directory
  # Overridden by var.user_data if explicitly set
  bootstrap_user_data = <<-EOF
    #!/bin/bash
    set -ex

    # Install prerequisites
    apt-get update -y
    apt-get install -y ca-certificates curl gnupg

    # Add Docker GPG key
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/debian/gpg \
      | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg

    # Add Docker apt repository
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
      https://download.docker.com/linux/debian \
      $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
      | tee /etc/apt/sources.list.d/docker.list > /dev/null

    # Install Docker Engine + Compose plugin
    apt-get update -y
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

    # Start Docker
    systemctl enable --now docker
    usermod -aG docker ${var.default_user}

    # Create service working directory
    mkdir -p /opt/${var.name}

    echo "Bootstrap complete" | tee -a /var/log/user-data.log
  EOF

  resolved_user_data = var.user_data != null ? var.user_data : local.bootstrap_user_data
}
