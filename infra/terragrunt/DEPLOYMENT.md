# 🚀 Drive-Ops Deployment Guide

This guide outlines the step-by-step process for deploying the Drive-Ops infrastructure from scratch. Due to strict resource dependencies (e.g., RDS requiring secrets from Shared Infra), the following sequence must be followed precisely.

## 📋 Prerequisites

* AWS CLI configured with appropriate permissions.
* Terragrunt and Terraform installed.
* A valid Discord Webhook URL for receiving alerts.

### 🏗️ Step 0: Environment Preparation

To prevent hardcoding sensitive data and to satisfy the fail-fast validation we implemented, you must export your Discord Webhook URL as an environment variable in your current terminal session.

```bash
# This variable is required by the Shared Infra module.
export TF_VAR_discord_webhook_url="https://discord.com/api/webhooks/your_actual_url_here"
```

#### 🔐 SSH Access Configuration (Bastion Host)

**⚠️ SECURITY NOTE:** The bastion host SSH allowlist (`BASTION_ALLOWED_SSH_CIDRS`) in `env_vars.yaml` contains a placeholder only. You MUST override this with your real IP address using one of the following methods:

1. **Environment Variable (Recommended for CI/CD):**
   ```bash
   export TG_VAR_BASTION_ALLOWED_SSH_CIDRS='["YOUR_IP/32"]'
   ```

2. **Local Override File (Recommended for local development):**
   Create a `.env_vars.local.yaml` file (already in `.gitignore`) in `infra/terragrunt/envs/dev/`:
   ```yaml
   BASTION_ALLOWED_SSH_CIDRS:
     - "YOUR_IP/32"
   ```

3. **AWS SSM Parameter Store (Recommended for production):**
   Store the CIDR list in SSM Parameter Store and update `bastion/terragrunt.hcl` to read from it.

**OWNER:** DevOps team  
**ROTATION:** Review quarterly or when team members change

### 🏗️ Step 1: Shared Infrastructure (Foundation)

This module sets up the core components: VPC, SQS queues, ECR repositories, and Secrets Manager.

```bash
cd /home/vlad/projects/drive-ops/infra/terragrunt/envs/dev/shared-infra
terragrunt apply -auto-approve
```

**Verification:** Check AWS Secrets Manager to ensure the secret `.../monitoring/discord` has been created with your real URL.

### 🗄️ Step 2: Database (Storage)

Now that the VPC and the master credentials secret are ready, deploy the RDS instance.

```bash
cd ../rds
terragrunt apply -auto-approve
```

**Note:** The RDS instance dynamically retrieves its master password from the secret created in Step 1.

### 🚀 Step 3: Application Services (Compute)

Once the foundation and monitoring are active, deploy the individual microservices.

```bash
# Run for each service in the following recommended order:
cd ../trip-service && terragrunt apply 
cd ../driver-service && terragrunt apply 
cd ../client-gateway && terragrunt apply
```

### 🛠️ Step 4: Post-Deployment Configuration (Scripts)

After the infrastructure is provisioned, you must initialize the application data and deploy specific image tags using the helper scripts.

**Navigate to the scripts directory:**
```bash
cd /home/vlad/projects/drive-ops/infra/scripts
```
**5.1 Initialize Database Schema**
```bash
./01-init-rds-schema.sh dev
```
**5.2 Populate SSM Parameters**
```bash
BOT_TOKEN=<your_token_here> ./02-populate-ssm.sh dev
```
**5.3 Deploy Application Images**
Use the image tag from ECR to deploy services.
```bash
./03-deploy-services.sh dev <tag> <service_name>
```
**5.4 Run Migrations**
```bash
./04-run-migrations.sh dev
```

### 📊 Step 5: Monitoring & Alerting

This module links the infrastructure together by creating CloudWatch Alarms and the Discord Lambda notifier.

```bash
cd ../monitoring
terragrunt apply -auto-approve
```

**Security:** The Lambda function uses Runtime Secret Resolution. It receives the Secret ARN via an environment variable and fetches the actual URL only when an alert is triggered.

### 🧪 Step 6: End-to-End Verification

To confirm that the entire alerting pipeline (CloudWatch → SNS → Lambda → Discord) is functional, trigger a manual alarm state.

```bash
aws cloudwatch set-alarm-state \
  --alarm-name "drive-ops-dev-rds-high-cpu" \
  --state-value ALARM \
  --state-reason "Testing Discord integration after security hardening."
```

## ✅ Deployment Checklist

* **Discord Integration:** You received a red notification in Discord regarding the ALARM.
* **Security Audit:** No plaintext URLs exist in the `terraform.tfstate` files or Lambda environment variables.
* **IAM Compliance:** All roles follow the `Training-` prefix naming convention to satisfy the DevOpsBound boundary.
* **Cost Efficiency:** CloudWatch log retention is set to 3 days to stay within the Free Tier.
