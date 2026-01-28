#!/bin/bash
set -e # Stop execution on the first error

echo "Running Infrastructure Checks for drive-ops..."

# 1. Terraform Formatting (recursive across all modules)
echo "Formatting Terraform code..."
terraform -chdir=terraform fmt -recursive

# 2. Terragrunt Formatting
echo "Formatting Terragrunt HCL files..."
terraform -chdir=terraform/bootstrap init -backend=false
terragrunt hclfmt --terragrunt-working-dir terragrunt

# 3. Bootstrap Validation (local)
echo "Validating Terraform bootstrap..."
terraform -chdir=terraform/bootstrap validate

# 4. Dev Environment Validation via Terragrunt
# Note: AWS credentials are required for full validation
echo "Validating Terragrunt dev environment..."
cd terragrunt/envs/dev && terragrunt run-all validate

echo "Infrastructure is clean and valid!"
