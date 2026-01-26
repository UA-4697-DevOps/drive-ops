# drive-ops Infrastructure (Terraform & Terragrunt)

This directory contains the IaC (Infrastructure as Code) baseline for the **drive-ops** project. It follows the best practices of separating resource definitions (Terraform modules) from environment configurations (Terragrunt).

## Prerequisites

- AWS CLI configured with valid credentials (`aws configure` or `aws sso login`)
- Terraform >= 1.0
- Terragrunt >= 0.45.0

Our remote state:
- S3 bucket: `drive-ops-dev-terraform-state`
- DynamoDB table: `drive-ops-dev-terraform-locks`

---

## Quick Start for DEV Environment

Once the state backend is bootstrapped, all operations are performed via **Terragrunt**:

### 1. Initialization
```bash
cd infra/terragrunt/envs/dev
terragrunt run-all init
```

### 2. Planning
```bash
terragrunt run-all plan
```

### 3. Applying Changes
```bash
terragrunt run-all apply
```

### 4. Destroying Resources
```bash
terragrunt run-all destroy
```

---

## Formatting and Validation

Before committing changes, ensure your code is properly formatted and validated:

### Format Terraform files
```bash
cd infra/terraform/modules/state-backend
terraform fmt -recursive
```

### Format Terragrunt files
```bash
cd infra/terragrunt
terragrunt hclfmt
```

### Validate Terraform configuration
```bash
cd infra/terraform/bootstrap
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
```

### Key Files

* **terraform/bootstrap/**: One-time Terraform setup to create S3 bucket and DynamoDB table for remote state
* **terraform/modules/**: Reusable Terraform modules
* **terragrunt/root.hcl**: Root configuration with remote state and provider setup
* **terragrunt/envs/common_vars.yaml**: Global variables shared across all environments
* **terragrunt/envs/dev/env_vars.yaml**: Development environment-specific variables
