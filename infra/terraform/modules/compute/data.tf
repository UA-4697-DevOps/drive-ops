data "aws_region" "current" {}

locals {
  resolved_ami = var.ami

  # Construct permissions boundary from account_id (DevOpsBound is required in this account)
  permissions_boundary = var.account_id != null ? "arn:aws:iam::${var.account_id}:policy/DevOpsBound" : null

  # Bootstrap user_data: install SSM Agent, Docker, and create service directory
  bootstrap_user_data = <<-EOF
    #!/bin/bash
    set -ex

    # 1. Install SSM Agent (Required for Debian 12/13 AMIs)
    mkdir -p /tmp/ssm
    curl https://s3.${data.aws_region.current.id}.amazonaws.com/amazon-ssm-${data.aws_region.current.id}/latest/debian_amd64/amazon-ssm-agent.deb -o /tmp/ssm/amazon-ssm-agent.deb
    # Use apt-get install to handle potential dependency issues automatically
    apt-get update -y
    apt-get install -y /tmp/ssm/amazon-ssm-agent.deb
    systemctl enable amazon-ssm-agent
    systemctl start amazon-ssm-agent

    # 2. Install Docker and Tools prerequisites
    # Added jq here to ensure it's available for the SSM deployment document
    apt-get install -y ca-certificates curl gnupg jq

    # 3. Add Docker GPG key
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/debian/gpg \
      | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg

    # 4. Add Docker apt repository
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
      https://download.docker.com/linux/debian \
      $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
      | tee /etc/apt/sources.list.d/docker.list > /dev/null

    # 5. Install Docker Engine
    apt-get update -y
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

    # 6. Final setup
    systemctl enable --now docker
    usermod -aG docker ${var.default_user}
    
    # This directory name now correctly includes the 'Training-' prefix from var.name
    mkdir -p /opt/${var.name}

    echo "Bootstrap complete" | tee -a /var/log/user-data.log
  EOF

  resolved_user_data = var.user_data != null ? var.user_data : local.bootstrap_user_data
}
