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

## Quick Start for DEV Environment
* terraform/modules/: Contains reusable "blueprints" (e.g., state-backend for S3/DynamoDB).

* terragrunt/envs/: Contains environment-specific configurations (dev, staging, etc.) and global variables.
