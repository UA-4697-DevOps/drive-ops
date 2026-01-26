# drive-ops Infrastructure (Terraform & Terragrunt)

This directory contains the IaC (Infrastructure as Code) baseline for the **drive-ops** project. It follows the best practices of separating resource definitions (Terraform modules) from environment configurations (Terragrunt).

## Quick Start for DEV Environment

All operations must be performed via **Terragrunt** from the specific environment directory to ensure proper state management and variable injection.



---

### 1. Initialization
Initializes the remote backend and downloads the required provider plugins:
```bash
cd infra/terragrunt/envs/dev
terragrunt run-all init
```

### 2. Planning (Plan)
Always verify the execution plan to see exactly what resources will be created, modified, or destroyed:
```bash
terragrunt run-all plan
```

### 3. Applying Changes (Apply)
Deploy the infrastructure to AWS:
```bash
terragrunt run-all apply
```

### 4. Destroying Resources (Destroy)
Use this command to tear down the infrastructure and avoid unnecessary AWS costs when the environment is no longer needed:
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
cd infra/terragrunt/envs/dev/state-backend
terragrunt validate
```

---

## Directory Structure

* **terraform/modules/**: Contains reusable Terraform modules (e.g., state-backend for S3/DynamoDB).

* **terragrunt/envs/**: Contains environment-specific configurations (dev, staging, etc.) and global variables.

* **terragrunt/envs/common_vars.yaml**: Global variables shared across all environments (project name, region, common tags).

* **terragrunt/envs/dev/env_vars.yaml**: Development environment-specific variables (env name, enable_ha flag, env-specific tags).

---

## First-Time Setup

When setting up a new environment for the first time, you must create the state backend infrastructure first:

### 1. Deploy the State Backend
```bash
cd infra/terragrunt/envs/dev/state-backend
terragrunt init
terragrunt apply
```

### 2. Deploy Other Infrastructure
Once the state backend is created, you can deploy other modules:
```bash
cd infra/terragrunt/envs/dev
terragrunt run-all init
terragrunt run-all apply
```
