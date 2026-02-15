resource "aws_ssm_document" "deploy_service" {
  count           = var.ecr_repository_url != null ? 1 : 0
  name            = "${var.name}-deploy"
  document_type   = "Command"
  document_format = "JSON"

  content = jsonencode({
    schemaVersion = "2.2"
    description   = "Deploy ${var.name} with SSM Config injection"
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
          # Set AWS CLI region explicitly to avoid configuration errors
          "export AWS_DEFAULT_REGION=${data.aws_region.current.name}",

          # 1. Login to ECR
          "echo 'Logging into ECR...'",
          "REGISTRY=$(echo '${var.ecr_repository_url}' | cut -d'/' -f1)",
          "aws ecr get-login-password | docker login --username AWS --password-stdin $REGISTRY",

          # 2. Prepare Directory
          "mkdir -p /opt/${var.name}",
          "cd /opt/${var.name}",

          # 3. Fetch Configuration from SSM Parameter Store
          # Critical step: fetch parameters configured by the deploy-config module and create .env file
          "echo 'Fetching configuration...'",
          "rm -f .env",

          # Install jq if missing (required for parsing AWS CLI JSON output)
          "command -v jq >/dev/null 2>&1 || apt-get install -y jq",

          # Get all parameters under /project/env/trip-service/
          # jq transforms /drive-ops/dev/trip-service/db-host -> DB_HOST=value
          # It splits by '/', takes the last part, uppercases it, and replaces hyphens with underscores
          "aws ssm get-parameters-by-path \\",
          "  --path /${var.project_name}/${var.env}/trip-service/ \\",
          "  --recursive \\",
          "  --with-decryption \\",
          "  --query \"Parameters[*].{Name:Name,Value:Value}\" \\",
          "  --output json | jq -r '.[] | (.Name | split(\"/\") | last | ascii_upcase | gsub(\"-\"; \"_\")) + \"=\" + .Value' > .env",

          # Add SQS URLs separately (they are located under /sqs/ path in deploy-config)
          "aws ssm get-parameters-by-path \\",
          "  --path /${var.project_name}/${var.env}/sqs/ \\",
          "  --recursive \\",
          "  --with-decryption \\",
          "  --query \"Parameters[*].{Name:Name,Value:Value}\" \\",
          "  --output json | jq -r '.[] | (.Name | split(\"/\") | last | ascii_upcase | gsub(\"-\"; \"_\")) + \"=\" + .Value' >> .env",

          # Add metadata
          "echo 'SERVICE_NAME=${var.name}' >> .env",

          # 4. Restart Container
          "echo 'Deploying new container version: {{ ImageTag }}...'",
          "docker stop ${var.name} || true",
          "docker rm ${var.name} || true",

          # Start container using --env-file to inject the fetched secrets
          "docker run -d \\",
          "  --name ${var.name} \\",
          "  --restart always \\",
          "  --env-file .env \\",
          "  -p ${var.app_port}:${var.app_port} \\",
          "  ${var.ecr_repository_url}:{{ ImageTag }}",

          "echo 'Deployment of ${var.name}:{{ ImageTag }} completed successfully.'"
        ]
      }
    }]
  })

  tags = var.tags
}

# State migration block (Keep as is)
moved {
  from = aws_ssm_document.deploy_service
  to   = aws_ssm_document.deploy_service[0]
}
