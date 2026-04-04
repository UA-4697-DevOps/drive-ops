# RDS Database Migrations Strategy

## Overview

This document defines the execution path for database migrations for the drive-ops microservices architecture deployed on AWS EC2 instances.

## Architecture

```
┌─────────────────────────────┐
│      Public Subnet          │
│  ┌─────────────────────┐    │
│  │ EC2 (public)        │    │
│  │ client-gateway bot  │    │
│  └─────────────────────┘    │
└─────────────────────────────┘
              │
              ↓
┌──────────────────────────────────────────┐
│         Private Subnet                   │
│  ┌─────────────────────┐                 │
│  │ EC2 (private)       │                 │
│  │ trip-service        │ ← PostgreSQL DB │
│  └─────────────────────┘     (RDS)      │
│                                          │
│  ┌─────────────────────┐                 │
│  │ EC2 (private)       │                 │
│  │ driver-service      │ ← PostgreSQL DB │
│  └─────────────────────┘     (RDS)      │
│                                          │
│  ┌─────────────────────┐                 │
│  │ RDS PostgreSQL      │                 │
│  │ Multi-database:     │                 │
│  │ - drive_ops_trip    │                 │
│  │ - drive_ops_driver  │                 │
│  └─────────────────────┘                 │
└──────────────────────────────────────────┘
```

## Current Migration Setup

Each service has its own migrations managed through Docker containers:

- **trip-service**: `Dockerfile.migrations` (golang-migrate)
- **driver-service**: `Dockerfile.migrations` (Alembic)

Local development uses init container pattern via `docker-compose.yml`:
```yaml
trip-migrations:
  build:
    dockerfile: Dockerfile.migrations
  depends_on:
    db:
      condition: service_healthy

trip-service:
  depends_on:
    trip-migrations:
      condition: service_completed_successfully
```

---

## Migration Execution Strategies

### Strategy 1: Init Container Pattern on EC2 (Recommended for Production)

Each EC2 instance runs migrations before starting the application service.

#### Implementation

**On each EC2 instance (trip-service, driver-service):**

Create `/opt/drive-ops/docker-compose.yml`:
```yaml
services:
  # Migration container runs first
  migrations:
    image: ghcr.io/your-org/trip-service-migrations:${APP_VERSION}
    container_name: trip-migrations
    environment:
      - SECRET_ARN=${RDS_SECRET_ARN}
      - DB_HOST=${DB_HOST}
      - DB_NAME=drive_ops_trip
      - AWS_REGION=us-east-2
    network_mode: host
    restart: "no"  # Run once and exit

  # Main application starts after migrations complete
  app:
    image: ghcr.io/your-org/trip-service:${APP_VERSION}
    container_name: trip-service
    environment:
      - SECRET_ARN=${RDS_SECRET_ARN}
      - DB_HOST=${DB_HOST}
      - DB_NAME=drive_ops_trip
      - RABBITMQ_HOST=${RABBITMQ_HOST}
    ports:
      - "8081:8081"
    depends_on:
      migrations:
        condition: service_completed_successfully
    restart: unless-stopped
```

**Deployment script on EC2** (`/opt/drive-ops/deploy.sh`):
```bash
#!/bin/bash
set -e

# Configuration
APP_VERSION=${1:-latest}
export APP_VERSION
export DB_HOST="drive-ops-dev-postgres.abc123.us-east-2.rds.amazonaws.com"
export RDS_SECRET_ARN="arn:aws:secretsmanager:us-east-2:ACCOUNT_ID:secret:drive-ops/dev/rds/credentials"
export RABBITMQ_HOST="rabbitmq.internal"

echo "Deploying trip-service version: $APP_VERSION"

# Pull latest images
docker-compose pull

# Stop current application (but keep data)
docker-compose down

# Run migrations + start new application
# Migrations will run first due to depends_on
docker-compose up -d

# Wait for health check
echo "Waiting for service to be healthy..."
timeout 60 bash -c 'until docker exec trip-service curl -f http://localhost:8081/health; do sleep 2; done'

echo "Deployment complete!"
```

**Update migration Dockerfile to fetch secrets** (`trip-service/Dockerfile.migrations`):
```dockerfile
FROM golang:1.21-alpine AS builder

# Install AWS CLI and jq for Secrets Manager
RUN apk add --no-cache aws-cli jq curl

WORKDIR /app

# Copy migration files
COPY migrations/ ./migrations/
COPY scripts/run-migrations.sh ./

RUN chmod +x run-migrations.sh

ENTRYPOINT ["./run-migrations.sh"]
```

**Migration entrypoint script** (`trip-service/scripts/run-migrations.sh`):
```bash
#!/bin/sh
set -e

echo "Starting database migrations..."

# Fetch credentials from Secrets Manager
if [ -n "$SECRET_ARN" ]; then
  echo "Fetching RDS credentials from Secrets Manager..."
  SECRET_JSON=$(aws secretsmanager get-secret-value \
    --secret-id "$SECRET_ARN" \
    --region "$AWS_REGION" \
    --query SecretString \
    --output text)

  DB_USER=$(echo "$SECRET_JSON" | jq -r '.username')
  DB_PASSWORD=$(echo "$SECRET_JSON" | jq -r '.password')
else
  echo "Using environment variables for DB credentials"
fi

# Build connection string
DATABASE_URL="postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:5432/${DB_NAME}?sslmode=require"

# Run migrations (adjust command based on your tool)
echo "Running migrations against $DB_HOST..."
migrate -path ./migrations -database "$DATABASE_URL" up

echo "✓ Migrations completed successfully"
```

**Pros:**
- ✅ Automatic - migrations run on every deployment
- ✅ Safe - app won't start if migrations fail
- ✅ Simple - same pattern as local development
- ✅ No external dependencies - works offline

**Cons:**
- ⚠️ Slower deployments (sequential execution)
- ⚠️ Need IAM permissions on EC2 for Secrets Manager

---

### Current Strategy: EKS-Based Migrations

Migrations are now executed via Kubernetes jobs running on EKS. This approach is centralized, scalable, and integrates with the ArgoCD GitOps workflow.

#### Implementation

Services deploy via ArgoCD, which manages Helm releases. Database migrations run as:
- **Helm hooks** (pre-install/pre-upgrade) for automatic migration execution
- **Kubernetes Jobs** for manual migration triggers

No EC2 deployment or manual SSH tunneling is required. All migrations execute within the EKS cluster with IRSA (IAM Roles for Service Accounts) providing AWS credentials.

**Advantages:**
- ✅ No EC2 infrastructure dependency
- ✅ Automatic migrations on ArgoCD sync
- ✅ Native Kubernetes integration
- ✅ Service account IAM permissions via IRSA
- ✅ Audit trail via ArgoCD and kubectl events

---

### Legacy: Strategy 2 (Deprecated)

**Cons:**
- ⚠️ Requires GitHub Actions to access RDS (via bastion/VPN)
- ⚠️ More complex setup (SSH tunneling, secrets management)
- ⚠️ GitHub Actions runner must have network path to RDS

---

### Strategy 3: Manual One-Off Migrations (Emergency/Hotfix)

For emergency migrations or manual testing before automated deployment.

#### Implementation

**Option A: From Bastion Host (Recommended)**

```bash
# 1. SSH to bastion host (public EC2)
ssh -i key.pem ec2-user@bastion-public-ip

# 2. Get RDS credentials
SECRET_ARN="arn:aws:secretsmanager:us-east-2:ACCOUNT_ID:secret:drive-ops/dev/rds/credentials"
SECRET=$(aws secretsmanager get-secret-value \
  --secret-id "$SECRET_ARN" \
  --query SecretString --output text)

DB_USER=$(echo $SECRET | jq -r '.username')
DB_PASS=$(echo $SECRET | jq -r '.password')
DB_HOST="drive-ops-dev-postgres.abc123.us-east-2.rds.amazonaws.com"

# 3. Run migration container
docker run --rm \
  -e DB_HOST=$DB_HOST \
  -e DB_USER=$DB_USER \
  -e DB_PASSWORD=$DB_PASS \
  -e DB_NAME=drive_ops_trip \
  ghcr.io/your-org/trip-service-migrations:latest
```

**Option B: From Trip Service EC2 (Directly)**

```bash
# 1. SSH to trip-service EC2 (through bastion)
ssh -i key.pem -J ec2-user@bastion-ip ec2-user@trip-service-private-ip

# 2. Run migrations
cd /opt/drive-ops
export SECRET_ARN="arn:aws:secretsmanager:us-east-2:ACCOUNT_ID:secret:drive-ops/dev/rds/credentials"
export DB_HOST="drive-ops-dev-postgres.abc123.us-east-2.rds.amazonaws.com"
docker-compose run --rm migrations
```

**Option C: Local Development with SSH Tunnel (Dev Only)**

```bash
# 1. Create SSH tunnel to RDS through bastion
ssh -i bastion.pem -L 5432:drive-ops-dev-postgres.abc123.us-east-2.rds.amazonaws.com:5432 ec2-user@bastion-ip

# 2. In another terminal, run migrations locally
cd trip-service
export DB_HOST=localhost
export DB_USER=driveops_admin
export DB_PASSWORD=<from-secrets-manager>
export DB_NAME=drive_ops_dev

# Run migrations
make migrate-up
# OR
docker-compose -f docker-compose.migrations.yml up
```

---

## Recommended Approach by Environment

| Environment | Primary Strategy | Backup Strategy |
|-------------|------------------|-----------------|
| **Local** | Init Container (docker-compose) | Manual (docker run) |
| **Dev** | Init Container on EC2 | CI/CD Job or Manual |
| **Prod** | CI/CD Job (GitHub Actions) | Manual via Bastion |

**Rationale:**
- **Dev:** Init container is simpler and faster for iteration
- **Prod:** CI/CD job provides better control, visibility, and rollback capability

---

## Migration Safety Best Practices

### 1. Backward-Compatible Migrations

Always deploy migrations that work with both old and new code versions:

**❌ Bad (Breaking Change):**
```sql
-- This immediately breaks old app version
ALTER TABLE trips DROP COLUMN old_status;
ALTER TABLE trips ADD COLUMN new_status VARCHAR(50);
```

**✅ Good (Zero-Downtime):**
```sql
-- Deployment 1: Add new column (old app ignores it)
ALTER TABLE trips ADD COLUMN new_status VARCHAR(50);

-- Deploy new app version (uses new_status, still reads old_status)

-- Deployment 2: Backfill data
UPDATE trips SET new_status = old_status WHERE new_status IS NULL;

-- Deployment 3 (later): Remove old column
ALTER TABLE trips DROP COLUMN old_status;
```

### 2. Migration Locking (Prevent Race Conditions)

If you scale to multiple EC2 instances, ensure only one runs migrations:

**For golang-migrate**, add to migration script:
```sql
-- migrations/001_add_lock.up.sql
SELECT pg_advisory_lock(123456789);  -- Acquire lock
-- Your actual migration here
SELECT pg_advisory_unlock(123456789);  -- Release lock
```

**For Alembic (Python):**
```python
# env.py
from alembic import context
from sqlalchemy import engine_from_config, pool, text
from logging.config import fileConfig

# ... other imports and config ...

def run_migrations_online():
    """Run migrations in 'online' mode with advisory lock."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # Acquire advisory lock before running migrations
        # Use a unique ID for your project (e.g., hash of project name)
        lock_id = 123456789

        try:
            print(f"Acquiring advisory lock {lock_id}...")
            connection.execute(text("SELECT pg_advisory_lock(:lock_id)"), {"lock_id": lock_id})
            print("Advisory lock acquired")

            context.configure(
                connection=connection,
                target_metadata=target_metadata
            )

            with context.begin_transaction():
                context.run_migrations()

        finally:
            # Always release the lock
            print(f"Releasing advisory lock {lock_id}...")
            connection.execute(text("SELECT pg_advisory_unlock(:lock_id)"), {"lock_id": lock_id})
            print("Advisory lock released")
```

### 3. Test Migrations Before Production

**Staging Environment Testing:**
```bash
# 1. Create snapshot of production RDS
aws rds create-db-snapshot \
  --db-instance-identifier drive-ops-prod-postgres \
  --db-snapshot-identifier prod-pre-migration-2024-02-02

# 2. Restore to staging
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier drive-ops-staging-test \
  --db-snapshot-identifier prod-pre-migration-2024-02-02

# 3. Run migrations in staging
ssh staging-ec2 "cd /opt/drive-ops && ./deploy.sh"

# 4. Verify application works
curl https://staging.driveops.com/health

# 5. If successful, proceed to production
```

### 4. Rollback Strategy

**Automatic Rollback in GitHub Actions:**
```yaml
- name: Run Migrations
  id: migrate
  run: ./run-migrations.sh up

- name: Deploy Application
  id: deploy
  run: ./deploy.sh

- name: Rollback on Failure
  if: failure() && steps.deploy.outcome == 'failure' && steps.migrate.outcome == 'success'
  run: ./run-migrations.sh down 1
```

**Manual Rollback:**
```bash
# For golang-migrate
migrate -path migrations -database $DATABASE_URL down 1

# For Alembic
alembic downgrade -1

# Always test rollback migrations in staging first!
```

### 5. Migration Monitoring

**CloudWatch Logs for Migration Container:**
```json
{
  "logConfiguration": {
    "logDriver": "awslogs",
    "options": {
      "awslogs-group": "/drive-ops/migrations",
      "awslogs-region": "us-east-2",
      "awslogs-stream-prefix": "trip-service"
    }
  }
}
```

**Slack/Email Alerts on Failure:**
```bash
# Add to run-migrations.sh
if ! migrate -path ./migrations -database "$DATABASE_URL" up; then
  aws sns publish \
    --topic-arn arn:aws:sns:us-east-2:ACCOUNT:migration-alerts \
    --subject "Migration Failed: trip-service" \
    --message "Database migration failed on $(hostname). Check logs."
  exit 1
fi
```

---

## IAM Permissions Required

### EC2 Instance Role

EC2 instances need permissions to:
1. Read from Secrets Manager (RDS credentials)
2. Pull Docker images from GitHub Container Registry

**IAM Policy** (`drive-ops-ec2-role-policy`):
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ReadRDSCredentials",
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": "arn:aws:secretsmanager:us-east-2:ACCOUNT_ID:secret:drive-ops/*/rds/credentials*"
    },
    {
      "Sid": "PullDockerImages",
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage"
      ],
      "Resource": "*"
    }
  ]
}
```

### GitHub Actions Role (for CI/CD strategy)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "rds:DescribeDBInstances",
        "secretsmanager:GetSecretValue"
      ],
      "Resource": "*"
    }
  ]
}
```

---

## Troubleshooting

### Issue: Migrations fail with "connection refused"

**Cause:** EC2 instance can't reach RDS

**Solution:**
1. Check security group allows traffic from EC2 to RDS on port 5432
2. Verify RDS is in same VPC as EC2
3. Test connectivity: `telnet rds-endpoint 5432`

### Issue: "Permission denied" accessing Secrets Manager

**Cause:** EC2 instance role lacks permissions

**Solution:**
```bash
# Verify instance has IAM role
aws sts get-caller-identity

# Check role has correct policy
aws iam list-attached-role-policies --role-name drive-ops-ec2-role
```

### Issue: Migration runs twice (concurrent execution)

**Cause:** Multiple EC2 instances running migrations simultaneously

**Solution:** Add advisory locks (see "Migration Locking" section above)

### Issue: "Secret not found" error

**Cause:** Wrong secret ARN or secret doesn't exist

**Solution:**
```bash
# List secrets
aws secretsmanager list-secrets

# Verify secret exists
aws secretsmanager get-secret-value \
  --secret-id drive-ops/dev/rds/credentials
```

---

## Next Steps

1. ✅ Update `Dockerfile.migrations` to fetch credentials from Secrets Manager
2. ✅ Test migrations locally with docker-compose
3. ✅ Set up IAM roles for EC2 instances
4. ✅ Create deployment scripts for each EC2 instance
5. ✅ Test full deployment flow in dev environment
6. ✅ Document rollback procedures in team runbook
7. ✅ Set up CloudWatch alarms for migration failures
