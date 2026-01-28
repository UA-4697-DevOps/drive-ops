# Terraform State Backend Bootstrap

This directory is used **once** to create the S3 bucket and DynamoDB table needed for Terraform remote state.

## Why Bootstrap?

This is a "chicken and egg" problem: Terraform needs an S3 bucket to store state, but we need to use Terraform to create that bucket. The solution is to create the state backend resources once using local state, then all other infrastructure can use remote state.

## Usage

### 1. Initialize Terraform (uses local state)
```bash
cd infra/terraform/bootstrap
terraform init
```

### 2. Review the plan
```bash
terraform plan
```

### 3. Create the state backend resources
```bash
terraform apply
```

This will create:
- S3 bucket: `drive-ops-dev-terraform-state`
- DynamoDB table: `drive-ops-dev-terraform-locks`

### 4. Verify outputs
```bash
terraform output
```

## After Bootstrap

Once the S3 bucket and DynamoDB table are created:

1. **Do NOT delete** the `terraform.tfstate` file in this directory (commit it to git)
2. All other infrastructure can now be deployed via Terragrunt with remote state
3. You only need to run this bootstrap process once per environment

## Destroying the Backend (⚠️ DANGEROUS)

If you need to tear down the entire infrastructure:

```bash
# First, destroy all other infrastructure via Terragrunt
cd ../../terragrunt/envs/dev
terragrunt run-all destroy

# Then destroy the state backend (⚠️ this will delete all state!)
cd ../../../terraform/bootstrap
terraform destroy
```

**Warning**: This will delete the S3 bucket containing all Terraform state. Make sure all other infrastructure is destroyed first!
