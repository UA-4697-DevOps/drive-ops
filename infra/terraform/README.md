# drive-ops Infrastructure (Terraform & Terragrunt)

This directory contains the IaC (Infrastructure as Code) baseline for the **drive-ops** project. It follows the best practices of separating resource definitions (Terraform modules) from environment configurations (Terragrunt).

## Prerequisites

- AWS CLI configured with valid credentials (`aws configure` or `aws sso login`)
- Terraform >= 1.0
- Terragrunt >= 0.45.0
- **Environment Variables**: You must have `AWS_ACCOUNT_ID` set in your active terminal.

1. **Create a `.env` file** in your project root (this file is ignored by Git):
```bash
   export AWS_ACCOUNT_ID="your_account_id_here"
   export AWS_REGION="us-east-2"
```
or
```bash
    source .env
```

Our remote state:
- S3 bucket: `drive-ops-dev-terraform-state`
- DynamoDB table: `drive-ops-dev-terraform-locks`

---

## Quick Start for DEV Environment

Once the state backend is bootstrapped, all operations are performed via **Terragrunt**:

### 0. Bootstrap
Terraform needs an S3 bucket to store its state. Run this manually first:
```bash
cd infra/terraform/bootstrap
terraform init
terraform apply
```

### 1. Initialization
```bash
terragrunt init
```

### 2. Planning
```bash
terragrunt plan
```

### 3. Applying Changes
```bash
terragrunt apply
```

### 4. Destroying Resources
```bash
terragrunt destroy
```

---

## Formatting and Validation

We use automated checks to ensure code quality before every commit.

### Automated Checks
The project is equipped with a Git pre-commit hook located in scripts/hooks/. It automatically runs all necessary checks before allowing a commit.

You can also trigger all checks manually using the global script from the infra/ directory:
```bash
./check-infra.sh
```
### Manual Commands
If you need to run specific checks individually:

### Format Terraform files
```bash
terraform fmt -recursive
```

### Format Terragrunt files
```bash
terragrunt hcl fmt
```

### Validate Terraform configuration
```bash
terraform validate
```

---

## Directory Structure

```
infra/
├── terraform/
│   ├── bootstrap/           # One-time setup for S3 + DynamoDB state backend
│   └── modules/
│       └── state-backend/   # Reusable state backend module
├── terragrunt/
│   ├── root.hcl            # Root Terragrunt configuration
│   └── envs/
│       ├── common_vars.yaml    # Global variables (project name, region, tags)
│       └── dev/
│           └── env_vars.yaml   # Dev-specific variables (env, enable_ha, etc.)
│           └── state-backend/
│               └── terragrunt.hcl
└── check-infra.sh  # Global validation script
```

### Key Files

* **terraform/bootstrap/**: One-time Terraform setup to create S3 bucket and DynamoDB table for remote state
* **terraform/modules/**: Reusable Terraform modules
* **terragrunt/root.hcl**: Root configuration with remote state and provider setup
* **terragrunt/envs/common_vars.yaml**: Global variables shared across all environments
* **terragrunt/envs/dev/env_vars.yaml**: Development environment-specific variables
