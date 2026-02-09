#!/bin/bash
set -e

apt-get update
apt-get install -y docker.io docker-compose awscli

systemctl enable docker
systemctl start docker

usermod -aG docker ubuntu

mkdir -p /opt/${service_name}

cat > /opt/${service_name}/docker-compose.yml << 'COMPOSE'
version: '3.8'

services:
  ${service_name}:
    image: $${ECR_REPOSITORY}:$${IMAGE_TAG}
    container_name: ${service_name}
    restart: unless-stopped
    ports:
      - "8082:8082"
    environment:
      - PYTHONUNBUFFERED=1
      - PYTHONPATH=/app/src
      - AWS_REGION=${aws_region}
    env_file:
      - .env
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8082/health"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 15s
COMPOSE

touch /opt/${service_name}/.env

echo "User data script completed"
