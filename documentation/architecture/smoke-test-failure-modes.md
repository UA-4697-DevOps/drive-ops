# Smoke Test Failure Modes — Common Diagnostics Guide

This document describes common failures that may occur during smoke testing of the drive-ops infrastructure in AWS.
Use the diagnostic table below for quick troubleshooting, then proceed to the detailed description for each failure mode.

---

## Quick Diagnostic Table

| **Symptom** | **Root Cause** | **How to Check** | **How to Fix** |
|---|---|---|---|
| `AccessDeniedException`<br/>`InvalidClientTokenId` | IAM role lacks SQS permissions | `aws sts get-caller-identity`<br/>`aws sqs get-queue-url --queue-name trip-created-dev.fifo` | Attach `*-consumer-policy` / `*-publisher-policy` to service role |
| RDS connection timeout<br/>(not refused, timeout) | Security Group blocks port 5432 | `aws ec2 describe-security-groups --group-ids <rds-sg-id>` | Add inbound rule for port 5432 from service SG |
| Services cannot reach each other<br/>(Client Gateway → Trip Service) | SG blocks traffic on 8080/8081/8082 | Check inbound rules in service SGs | Add ingress rules between service SGs |
| `NonExistentQueue`<br/>`QueueDoesNotExist` | Invalid queue URLs in env vars | `aws sqs get-queue-url --queue-name trip-created-dev.fifo --region us-east-2` | Update `SQS_*_QUEUE_URL` from Terraform output |
| Queue URL missing `.fifo` suffix | Using standard queue instead of FIFO | Check `.fifo` suffix in env vars | Fix URL — FIFO queues must have `.fifo` suffix |
| `FATAL: password authentication failed` | Invalid RDS credentials | `aws secretsmanager get-secret-value --secret-id drive-ops/<env>/rds-credentials` | Sync password between Secrets Manager & env |
| HTTP 500 / Cannot create trip | Migrations not applied — tables missing | `\dt` in psql via bastion / check migration logs | Run migrations manually |
| Timeout at `sqs:GetQueueUrl` | No NAT Instance or VPC Endpoint for SQS | `aws ec2 describe-vpc-endpoints --filters "Name=vpc-id,Values=<vpc-id>"` | Add VPC Endpoint for SQS or enable NAT Instance |
| `InvalidParameterValue`<br/>Resource not found | Region mismatch | Compare `AWS_REGION` with `terraform show | grep region` | Set `AWS_REGION=us-east-2` for all services |

---

## 1. IAM Permissions

### Symptom

Driver Service or Trip Service crash on startup with `AccessDeniedException` or `InvalidClientTokenId` in logs.

### Root Cause

The IAM role (EC2/ECS task) lacks required permissions: `sqs:SendMessage`, `sqs:ReceiveMessage`, `sqs:DeleteMessage`, `sqs:GetQueueUrl`, `sqs:GetQueueAttributes` for the respective queues.

### How to Check

```bash
# Check which IAM role is being used
aws sts get-caller-identity

# Verify access to a queue
aws sqs get-queue-url --queue-name trip-created-dev.fifo
```

### How to Fix

Review the Terraform `sqs` module — it creates IAM policies `*-consumer-policy` and `*-publisher-policy`. Ensure these policies are attached to the service role.

Required permissions per service:

| Service | Required SQS Actions |
|---------|----------------------|
| Trip Service (publisher) | `sqs:SendMessage`, `sqs:GetQueueUrl` |
| Driver Service (consumer) | `sqs:ReceiveMessage`, `sqs:DeleteMessage`, `sqs:GetQueueUrl`, `sqs:GetQueueAttributes` |

---

## 2. Security Group Rules

### Symptom

Service cannot connect to RDS — connection timeout (not refused, but timeout).

### Root Cause

RDS Security Group doesn't allow inbound traffic on port 5432 from the service Security Group.

### How to Check

```bash
# Review inbound rules for RDS SG
aws ec2 describe-security-groups --group-ids <rds-sg-id>
```

### How to Fix

In the Terraform `vpc` module, configure security groups. Ensure RDS SG allows ingress on port `5432` from the service SG.

### Additional Case: Services Cannot Reach Each Other

**Symptom**: Client Gateway cannot connect to Trip Service or Driver Service.

**Root Cause**: SG doesn't allow traffic on ports 8080/8081/8082 between services.

**How to Check**: Verify inbound rules in service SGs — each service must allow ingress on its port from other services' SGs.

| Service | Port | Should Accept From |
|---------|------|-------------------|
| Client Gateway | 8080 | External traffic / ALB |
| Trip Service | 8081 | Client Gateway, Driver Service |
| Driver Service | 8082 | Client Gateway, Trip Service |

---

## 3. Wrong Queue URLs

### Symptom

Service starts but messages don't flow. Logs show `NonExistentQueue` or `QueueDoesNotExist`.

### Root Cause

Environment variables `SQS_TRIP_CREATED_QUEUE_URL`, `SQS_DRIVER_ASSIGNED_QUEUE_URL`, `SQS_TRIP_COMPLETED_QUEUE_URL` point to non-existent or wrong-region queues.

### How to Check

```bash
# Verify actual queue URL
aws sqs get-queue-url --queue-name trip-created-dev.fifo --region us-east-2

# Compare with service env vars
```

### How to Fix

Queue URL must be in the format:
```
https://sqs.us-east-2.amazonaws.com/<account-id>/trip-created-<env>.fifo
```

Ensure Terraform `sqs` module outputs are passed to service configuration.

### Additional Case: Standard Queue Instead of FIFO

**Symptom**: Publishing messages fails, but the queue exists.

**Root Cause**: Using a standard queue URL instead of FIFO.

**How to Check**: FIFO queues **must** have the `.fifo` suffix in the name. Verify URL ends with `.fifo`.

Project queue naming convention:
- `trip-created-<env>.fifo`
- `driver-assigned-<env>.fifo`
- `trip-completed-<env>.fifo`

---

## 4. Missing Secrets (RDS Credentials)

### Symptom

Service crashes with:
```
OperationalError: could not connect to server: FATAL: password authentication failed
```

### Root Cause

Environment variables `DB_USER` and `DB_PASSWORD` are missing or incorrect. Or the secret in AWS Secrets Manager is not created / has wrong version.

### How to Check

```bash
# Verify secret exists and is current
aws secretsmanager get-secret-value --secret-id drive-ops/<env>/rds-credentials
```

Compare password from Secrets Manager with what the service uses.

### How to Fix

The Terraform `secrets` module auto-generates a 32-character password. Possible scenarios:

1. **Password changed manually in RDS** but not updated in Secrets Manager → update the secret in Secrets Manager.
2. **Service doesn't read from Secrets Manager**, uses env vars → ensure env vars are current.
3. **Secret not created** → run `terraform apply` for the `secrets` module.

---

## 5. Database / Migrations Issues

### Symptom

Service starts but returns HTTP 500 or cannot create a trip.

### Root Cause

Migrations not applied — tables `trips`, `drivers`, or `bot_users` don't exist.

### How to Check

```bash
# Connect to RDS via bastion and verify tables
psql -h <rds-endpoint> -U <user> -d trip_db -c "\dt"
psql -h <rds-endpoint> -U <user> -d driver_db -c "\dt"
```

Or check migration container logs:
```bash
# For ECS
aws ecs describe-tasks --cluster <cluster> --tasks <migration-task-id>
aws logs get-log-events --log-group-name <log-group> --log-stream-name <stream>
```

Expected tables:
- `trip_db`: `trips`
- `driver_db`: `drivers`, `bot_users`

### How to Fix

Run migrations manually:

```bash
# Trip Service (Go migrate)
migrate -path db/migrations -database "$DATABASE_URL" up

# Driver Service (Alembic)
alembic upgrade head
```

---

## 6. Network / VPC Issues

### Symptom

Service cannot connect to SQS — timeout at `sqs:GetQueueUrl`.

### Root Cause

Service is in a private subnet without NAT Instance or VPC Endpoint for SQS.

### How to Check

```bash
# Verify VPC Endpoint for SQS exists
aws ec2 describe-vpc-endpoints \
  --filters "Name=vpc-id,Values=<vpc-id>" \
  --query "VpcEndpoints[?ServiceName=='com.amazonaws.us-east-2.sqs']"
```

### How to Fix

Choose one of two options:

1. **VPC Endpoint for SQS** (recommended) — add Interface VPC Endpoint for `com.amazonaws.us-east-2.sqs` in private subnets.
2. **NAT Instance** — enable NAT Instance (`use_nat_instance = true`) in the VPC module to route private subnet traffic to the internet.

> **Note**: VPC Endpoint is more secure — traffic stays within AWS network. However, cost comparisons depend on traffic volume, number of AZs, and the chosen NAT Instance size. For example, a small NAT Instance (e.g., t3.nano) can be cheaper than an interface VPC Endpoint with per‑AZ hourly and per‑GB charges at low SQS volumes. Evaluate per‑GB and per‑AZ costs when choosing between VPC Endpoint and NAT Instance.

---

## 7. Region Mismatch

### Symptom

`InvalidParameterValue` or resource not found when accessing SQS/RDS.

### Root Cause

`AWS_REGION` in service configuration doesn't match the region where SQS queues or RDS are created. This project uses `us-east-2`.

### How to Check

```bash
# Check region in Terraform state
terraform show | grep region

# Compare with AWS_REGION in service env
echo $AWS_REGION
```

### How to Fix

Set the same `AWS_REGION=us-east-2` for all services. Verify:

- `AWS_REGION` / `AWS_DEFAULT_REGION` = `us-east-2` in each service's env
- Queue URLs contain `us-east-2` (e.g., `https://sqs.us-east-2.amazonaws.com/...`)
- RDS endpoint matches region `us-east-2`
