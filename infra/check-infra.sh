#!/bin/bash
# Stop execution on the first error
set -e 

echo "🔍 Running Infrastructure Checks for drive-ops..."

# 1. Formatting
echo "🎨 Formatting all HCL and Terraform code..."
# Recursively formats all files in the infra directory
terraform fmt -recursive infra/

# 2. Bootstrap Validation
echo "✅ Validating Terraform bootstrap..."
# Initialize modules locally without connecting to an AWS backend
terraform -chdir=infra/terraform/bootstrap init -backend=false
terraform -chdir=infra/terraform/bootstrap validate

# 3. Dev Environment Validation via Terragrunt
echo "✅ Validating Terragrunt dev environment..."
# Terragrunt handles initialization automatically, so no extra init command is needed
(cd infra/terragrunt/envs/dev/state-backend && terragrunt run -- validate)

# 4. Networking Validation via Terragrunt
echo "✅ Validating Terragrunt networking..."
(cd infra/terragrunt/envs/dev/vpc && terragrunt run -- validate)

echo "🚀 Infrastructure is clean and valid!"
