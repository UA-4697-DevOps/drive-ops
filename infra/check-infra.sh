#!/bin/bash
set -e # Stop execution on the first error

# Navigate to the project root
cd "$(dirname "$0")/.."

echo "🔍 Running Infrastructure Checks for drive-ops..."

# 1. Formatting
echo "🎨 Formatting Terraform code..."
terraform fmt -recursive infra/

# 2. Bootstrap Validation
echo "✅ Validating Terraform bootstrap..."
terraform -chdir=infra/terraform/bootstrap init -backend=false
terraform -chdir=infra/terraform/bootstrap validate

# 3. Dev Environment Validation
echo "✅ Validating Terragrunt modules in Dev..."

for dir in infra/terragrunt/envs/dev/*/; do
    if [ -f "$dir/terragrunt.hcl" ]; then
        module_name=$(basename "$dir")
        
        # Check if the file actually has a source defined.
        # This prevents the "Did not find any Terraform files" error on empty modules.
        if grep -q "source =" "$dir/terragrunt.hcl"; then
            echo "   👉 Validating module: $module_name..."
            # We use '|| true' or a specific check if you want the script 
            # to keep going even if a teammate's module (like RDS) is broken.
            (cd "$dir" && terragrunt validate > /dev/null)
        else
            echo "   ⏩ Skipping uninitialized module: $module_name"
        fi
    fi
done

echo "🚀 Infrastructure is clean and valid!"
