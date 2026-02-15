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
          # Write secrets to a temp file with restricted permissions, then
          # atomically replace .env so secrets are never world-readable on disk.
          "echo 'Fetching configuration...'",

          # Install jq if missing (required for parsing AWS CLI JSON output)
          "command -v jq >/dev/null 2>&1 || apt-get install -y jq",

          # Restrict permissions: new files created in this subshell get 600
          "( umask 0077",

          # Write service-specific params to temp file
          # jq transforms /drive-ops/dev/driver-service/database-url -> DATABASE_URL=value
          "  aws ssm get-parameters-by-path \\",
          "    --path /${var.project_name}/${var.env}/${var.service_name}/ \\",
          "    --recursive \\",
          "    --with-decryption \\",
          "    --query \"Parameters[*].{Name:Name,Value:Value}\" \\",
          "    --output json | jq -r '.[] | (.Name | split(\"/\") | last | ascii_upcase | gsub(\"-\"; \"_\")) + \"=\" + .Value' > .env.tmp",

          # Append shared SQS URLs
          "  aws ssm get-parameters-by-path \\",
          "    --path /${var.project_name}/${var.env}/sqs/ \\",
          "    --recursive \\",
          "    --with-decryption \\",
          "    --query \"Parameters[*].{Name:Name,Value:Value}\" \\",
          "    --output json | jq -r '.[] | (.Name | split(\"/\") | last | ascii_upcase | gsub(\"-\"; \"_\")) + \"=\" + .Value' >> .env.tmp",

          # Append metadata
          "  echo 'SERVICE_NAME=${var.name}' >> .env.tmp",

          # Explicit safety net in case umask was overridden externally
          "  chmod 600 .env.tmp",

          # Atomic replace: container never reads a partially-written file
          "  mv -f .env.tmp .env",
          ")",

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
