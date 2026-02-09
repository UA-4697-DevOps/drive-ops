data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

resource "aws_iam_role" "ec2_ssm_role" {
  name                 = "${var.project_name}-${var.env}-${var.service_name}-ec2-role"
  permissions_boundary = "arn:aws:iam::${var.account_id}:policy/DevOpsBound"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ec2.amazonaws.com"
      }
    }]
  })

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "ssm_managed_instance" {
  role       = aws_iam_role.ec2_ssm_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_policy" "ecr_pull" {
  name        = "${var.project_name}-${var.env}-${var.service_name}-ecr-pull"
  description = "Allow EC2 to pull images from ECR"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ecr_pull" {
  role       = aws_iam_role.ec2_ssm_role.name
  policy_arn = aws_iam_policy.ecr_pull.arn
}

resource "aws_iam_instance_profile" "ec2_profile" {
  name = "${var.project_name}-${var.env}-${var.service_name}-profile"
  role = aws_iam_role.ec2_ssm_role.name

  tags = var.tags
}

resource "aws_instance" "docker_host" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.instance_type
  subnet_id              = var.subnet_id
  vpc_security_group_ids = [var.security_group_id]
  iam_instance_profile   = aws_iam_instance_profile.ec2_profile.name
  key_name               = var.key_name
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }
  root_block_device {
    encrypted = true
  }
  user_data = templatefile("${path.module}/user-data.sh", {
    service_name = var.service_name
    aws_region   = var.aws_region
  })
  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.env}-${var.service_name}-host"
  })
}

resource "aws_ssm_document" "deploy_service" {
  name            = "${var.project_name}-${var.env}-${var.service_name}-deploy"
  document_type   = "Command"
  document_format = "YAML"

  content = <<-DOC
schemaVersion: '2.2'
description: Deploy driver-service using Docker Compose
parameters:
  ImageTag:
    type: String
    description: Docker image tag to deploy
    default: latest
  EcrRepository:
    type: String
    description: ECR repository URL
mainSteps:
  - action: aws:runShellScript
    name: deployService
    inputs:
      runCommand:
        - |
          set -e
          cd /opt/${var.service_name}
          
          export IMAGE_TAG={{ ImageTag }}
          export ECR_REPOSITORY={{ EcrRepository }}
          
          aws ecr get-login-password --region ${var.aws_region} | docker login --username AWS --password-stdin {{ EcrRepository }}
          
          docker-compose pull
          docker-compose up -d
          
          echo "Deployment completed successfully"
DOC

  tags = var.tags
}
