resource "aws_ssm_document" "deploy_service" {
  count           = var.ecr_repository_url != null ? 1 : 0
  name            = "${var.name}-deploy"
  document_type   = "Command"
  document_format = "JSON"

  content = jsonencode({
    schemaVersion = "2.2"
    description   = "Deploy ${var.name} using Docker Compose"
    parameters = {
      ImageTag = {
        type        = "String"
        description = "Docker image tag to deploy"
        default     = "latest"
      }
    }
    mainSteps = [{
      action = "aws:runShellScript"
      name   = "deployService"
      inputs = {
        runCommand = [
          "set -e",
          "REGISTRY=$(echo '${var.ecr_repository_url}' | cut -d'/' -f1)",
          "aws ecr get-login-password --region ${data.aws_region.current.name} | docker login --username AWS --password-stdin $REGISTRY",
          "cd /opt/${var.name}",
          "export IMAGE_TAG={{ ImageTag }}",
          "docker compose pull",
          "docker compose up -d --remove-orphans",
          "echo 'Deployment of ${var.name}:{{ ImageTag }} completed'"
        ]
      }
    }]
  })

  tags = var.tags
}

# State migration: client-gateway had this resource without count index
moved {
  from = aws_ssm_document.deploy_service
  to   = aws_ssm_document.deploy_service[0]
}
