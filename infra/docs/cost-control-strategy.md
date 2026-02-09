# Infrastructure Cost Control Strategy

## Overview

This document outlines start/stop/destroy strategies to control AWS infrastructure costs for the drive-ops project, particularly for development and staging environments.

---

## Cost Breakdown

**Monthly estimates for dev environment:**

| Resource | Type | Running 24/7 | Running 8h/day | Notes |
|----------|------|--------------|----------------|-------|
| RDS PostgreSQL | db.t3.micro | ~$15/month | ~$5/month | Main cost driver |
| EC2 - Client Gateway | t3.micro | ~$7.50/month | ~$2.50/month | Public instance |
| EC2 - Trip Service | t3.micro | ~$7.50/month | ~$2.50/month | Private instance |
| EC2 - Driver Service | t3.micro | ~$7.50/month | ~$2.50/month | Private instance |
| S3 (Terraform state) | Standard | ~$0.10/month | ~$0.10/month | Minimal |
| DynamoDB (state lock) | On-demand | ~$0.50/month | ~$0.50/month | Minimal |
| **Total** | | **~$38/month** | **~$13/month** | **66% savings** |

**Savings opportunity:** Stop dev environment outside working hours (9 AM - 5 PM, weekdays)
- **Potential savings:** ~$25/month per environment

---

## Strategy 1: Stop/Start RDS Instance

RDS can be stopped for up to **7 days**. After 7 days, AWS automatically starts it.

### Manual Stop/Start

**Stop RDS:**
```bash
# Stop the RDS instance (free for 7 days)
aws rds stop-db-instance \
  --db-instance-identifier drive-ops-dev-postgres \
  --region us-east-2

# Check status
aws rds describe-db-instances \
  --db-instance-identifier drive-ops-dev-postgres \
  --query 'DBInstances[0].DBInstanceStatus' \
  --output text
```

**Start RDS:**
```bash
# Start the RDS instance
aws rds start-db-instance \
  --db-instance-identifier drive-ops-dev-postgres \
  --region us-east-2

# Wait for it to be available (takes ~2-3 minutes)
aws rds wait db-instance-available \
  --db-instance-identifier drive-ops-dev-postgres
```

**Important Notes:**
- ✅ Stopped instances don't incur compute charges (still pay for storage)
- ⚠️ AWS auto-starts after 7 days
- ⚠️ Stopping causes brief downtime (~1-2 minutes)
- ⚠️ Connection endpoint remains the same

---

### Automated Stop/Start with Lambda

**Use Case:** Automatically stop RDS outside working hours

**Architecture:**
```
EventBridge Rule (cron)
  ↓
Lambda Function
  ↓
Stop/Start RDS Instance
  ↓
SNS Notification (optional)
```

#### Implementation

**1. Lambda Function** (`infra/lambda/rds-scheduler.py`):
```python
import boto3
import os
from datetime import datetime

rds = boto3.client('rds')
sns = boto3.client('sns')

DB_INSTANCE_ID = os.environ['DB_INSTANCE_ID']
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN')

def lambda_handler(event, context):
    action = event.get('action', 'stop')  # 'start' or 'stop'

    try:
        # Get current status
        response = rds.describe_db_instances(DBInstanceIdentifier=DB_INSTANCE_ID)
        current_status = response['DBInstances'][0]['DBInstanceStatus']

        print(f"Current RDS status: {current_status}")

        if action == 'stop':
            if current_status == 'available':
                rds.stop_db_instance(DBInstanceIdentifier=DB_INSTANCE_ID)
                message = f"✅ RDS instance {DB_INSTANCE_ID} stopped successfully"
            else:
                message = f"⚠️ RDS instance {DB_INSTANCE_ID} is {current_status}, cannot stop"

        elif action == 'start':
            if current_status == 'stopped':
                rds.start_db_instance(DBInstanceIdentifier=DB_INSTANCE_ID)
                message = f"✅ RDS instance {DB_INSTANCE_ID} started successfully"
            else:
                message = f"⚠️ RDS instance {DB_INSTANCE_ID} is {current_status}, cannot start"

        print(message)

        # Send notification
        if SNS_TOPIC_ARN:
            sns.publish(
                TopicArn=SNS_TOPIC_ARN,
                Subject=f"RDS Scheduler: {action.upper()}",
                Message=message
            )

        return {'statusCode': 200, 'body': message}

    except Exception as e:
        error_message = f"❌ Error: {str(e)}"
        print(error_message)

        if SNS_TOPIC_ARN:
            sns.publish(
                TopicArn=SNS_TOPIC_ARN,
                Subject="RDS Scheduler: ERROR",
                Message=error_message
            )

        return {'statusCode': 500, 'body': error_message}
```

**2. Terraform Module** (`infra/terraform/modules/rds-scheduler/main.tf`):
```hcl
resource "aws_lambda_function" "rds_scheduler" {
  filename         = "rds-scheduler.zip"
  function_name    = "${var.project_name}-${var.env}-rds-scheduler"
  role            = aws_iam_role.lambda.arn
  handler         = "rds-scheduler.lambda_handler"
  runtime         = "python3.11"
  timeout         = 60

  environment {
    variables = {
      DB_INSTANCE_ID = var.db_instance_id
      SNS_TOPIC_ARN  = var.sns_topic_arn
    }
  }
}

# Stop RDS at 6 PM UTC (weekdays)
resource "aws_cloudwatch_event_rule" "stop_rds" {
  name                = "${var.project_name}-${var.env}-stop-rds"
  description         = "Stop RDS instance at 6 PM UTC on weekdays"
  schedule_expression = "cron(0 18 ? * MON-FRI *)"
}

resource "aws_cloudwatch_event_target" "stop_rds" {
  rule      = aws_cloudwatch_event_rule.stop_rds.name
  target_id = "StopRDS"
  arn       = aws_lambda_function.rds_scheduler.arn
  input     = jsonencode({ action = "stop" })
}

# Start RDS at 8 AM UTC (weekdays)
resource "aws_cloudwatch_event_rule" "start_rds" {
  name                = "${var.project_name}-${var.env}-start-rds"
  description         = "Start RDS instance at 8 AM UTC on weekdays"
  schedule_expression = "cron(0 8 ? * MON-FRI *)"
}

resource "aws_cloudwatch_event_target" "start_rds" {
  rule      = aws_cloudwatch_event_rule.start_rds.name
  target_id = "StartRDS"
  arn       = aws_lambda_function.rds_scheduler.arn
  input     = jsonencode({ action = "start" })
}

# IAM Role for Lambda
resource "aws_iam_role" "lambda" {
  name = "${var.project_name}-${var.env}-rds-scheduler-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "lambda" {
  name = "rds-scheduler-policy"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "rds:DescribeDBInstances",
          "rds:StartDBInstance",
          "rds:StopDBInstance"
        ]
        Resource = "arn:aws:rds:${var.aws_region}:*:db:${var.db_instance_id}"
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = ["sns:Publish"]
        Resource = var.sns_topic_arn
      }
    ]
  })
}

resource "aws_lambda_permission" "allow_eventbridge_stop" {
  statement_id  = "AllowExecutionFromEventBridgeStop"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.rds_scheduler.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.stop_rds.arn
}

resource "aws_lambda_permission" "allow_eventbridge_start" {
  statement_id  = "AllowExecutionFromEventBridgeStart"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.rds_scheduler.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.start_rds.arn
}
```

**Schedule Examples:**
- **Stop at 6 PM weekdays:** `cron(0 18 ? * MON-FRI *)`
- **Start at 8 AM weekdays:** `cron(0 8 ? * MON-FRI *)`
- **Stop on Friday 6 PM:** `cron(0 18 ? * FRI *)`
- **Start on Monday 8 AM:** `cron(0 8 ? * MON *)`

---

## Strategy 2: Stop/Start EC2 Instances

EC2 instances can be stopped anytime. You only pay for EBS storage when stopped.

### Manual Stop/Start

**Stop all instances:**
```bash
# Stop client-gateway (public EC2)
aws ec2 stop-instances --instance-ids i-client-gateway-id

# Stop trip-service (private EC2)
aws ec2 stop-instances --instance-ids i-trip-service-id

# Stop driver-service (private EC2)
aws ec2 stop-instances --instance-ids i-driver-service-id

# Check status
aws ec2 describe-instances \
  --instance-ids i-client-gateway-id i-trip-service-id i-driver-service-id \
  --query 'Reservations[].Instances[].[InstanceId,State.Name]' \
  --output table
```

**Start all instances:**
```bash
aws ec2 start-instances \
  --instance-ids i-client-gateway-id i-trip-service-id i-driver-service-id

# Wait for them to be running
aws ec2 wait instance-running \
  --instance-ids i-client-gateway-id i-trip-service-id i-driver-service-id
```

**Important Notes:**
- ✅ Stopped instances don't incur compute charges
- ✅ Private IP addresses remain the same
- ⚠️ Public IP address changes (use Elastic IP to prevent this)
- ⚠️ Applications need to be restarted after boot

---

### Automated EC2 Scheduling with Instance Scheduler

**AWS Instance Scheduler** - official AWS solution for scheduling EC2/RDS start/stop

**Setup:**
```bash
# Deploy Instance Scheduler CloudFormation stack
aws cloudformation create-stack \
  --stack-name drive-ops-instance-scheduler \
  --template-url https://s3.amazonaws.com/solutions-reference/aws-instance-scheduler/latest/instance-scheduler.template \
  --parameters \
    ParameterKey=DefaultTimezone,ParameterValue=UTC \
    ParameterKey=SchedulingActive,ParameterValue=Yes \
  --capabilities CAPABILITY_IAM
```

**Tag EC2 instances:**
```bash
# Tag for weekday 8 AM - 6 PM schedule
aws ec2 create-tags \
  --resources i-client-gateway-id i-trip-service-id i-driver-service-id \
  --tags Key=Schedule,Value=dev-hours
```

**Create schedule in DynamoDB:**
```json
{
  "name": "dev-hours",
  "periods": [
    {
      "name": "working-hours",
      "begintime": "08:00",
      "endtime": "18:00",
      "weekdays": ["mon-fri"]
    }
  ]
}
```

---

## Strategy 3: Destroy and Recreate (Full Teardown)

For long-term cost savings (weekends, holidays, end of sprint).

### Pre-Destroy Checklist

**1. Create RDS Snapshot (for data retention):**
```bash
# Create manual snapshot
aws rds create-db-snapshot \
  --db-instance-identifier drive-ops-dev-postgres \
  --db-snapshot-identifier drive-ops-dev-snapshot-$(date +%Y%m%d)

# Wait for completion
aws rds wait db-snapshot-completed \
  --db-snapshot-identifier drive-ops-dev-snapshot-$(date +%Y%m%d)

# List snapshots
aws rds describe-db-snapshots \
  --db-instance-identifier drive-ops-dev-postgres
```

**2. Export important data (if needed):**
```bash
# Dump database
pg_dump -h drive-ops-dev-postgres.abc123.us-east-2.rds.amazonaws.com \
  -U driveops_admin -d drive_ops_dev > backup.sql

# Upload to S3
aws s3 cp backup.sql s3://drive-ops-backups/dev/$(date +%Y%m%d).sql
```

---

### Destroy Infrastructure

**Option A: Destroy specific environment with Terragrunt:**
```bash
cd infra/terragrunt/envs/dev

# Destroy in reverse order (dependencies)
cd rds && terragrunt destroy --auto-approve
cd ../secrets && terragrunt destroy --auto-approve
cd ../vpc && terragrunt destroy --auto-approve

# Or destroy everything at once (careful!)
terragrunt run-all destroy
```

**Option B: Destroy via AWS CLI (manual cleanup):**
```bash
# Delete RDS (skip final snapshot for dev)
aws rds delete-db-instance \
  --db-instance-identifier drive-ops-dev-postgres \
  --skip-final-snapshot

# Terminate EC2 instances
aws ec2 terminate-instances \
  --instance-ids i-client-gateway-id i-trip-service-id i-driver-service-id

# Delete security groups, subnets, VPC (after resources deleted)
# ... manual cleanup
```

---

### Recreate from Snapshot

**1. Restore RDS from snapshot:**
```bash
# Restore RDS instance
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier drive-ops-dev-postgres \
  --db-snapshot-identifier drive-ops-dev-snapshot-20240202 \
  --db-subnet-group-name drive-ops-dev-db-subnet-group \
  --vpc-security-group-ids sg-db-id

# Wait for it to be available (takes ~5-10 minutes)
aws rds wait db-instance-available \
  --db-instance-identifier drive-ops-dev-postgres
```

**2. Recreate infrastructure with Terragrunt:**
```bash
cd infra/terragrunt/envs/dev

# Apply in order
cd vpc && terragrunt apply --auto-approve
cd ../secrets && terragrunt apply --auto-approve
# Skip RDS if restored from snapshot manually

# Or recreate everything
terragrunt run-all apply
```

---

## Strategy Comparison

| Strategy | Cost Savings | Data Retained | Recovery Time | Complexity |
|----------|--------------|---------------|---------------|------------|
| Stop/Start RDS | ~50% | ✅ Yes | 2-3 minutes | Low |
| Stop/Start EC2 | ~25% | ✅ Yes (EBS) | 1-2 minutes | Low |
| Automated Scheduler | ~60-70% | ✅ Yes | Automatic | Medium |
| Full Destroy | ~95% | ⚠️ Only with snapshot | 10-15 minutes | High |

---

## Recommended Strategies by Environment

### Dev Environment

**Daily (weekdays):**
- Use automated scheduler for RDS + EC2
- **Schedule:** Run 8 AM - 6 PM UTC (working hours)
- **Expected savings:** ~65%

**Weekends:**
- Keep infrastructure stopped
- Start manually if needed for demos/testing

**Long holidays:**
- Full destroy + snapshot
- Recreate when needed

### Staging Environment

**During active development:**
- Keep running 24/7 for automated tests

**Between sprints:**
- Stop RDS + EC2 outside working hours
- Use scheduler: 6 AM - 10 PM UTC

**End of project phase:**
- Full destroy + snapshot
- Restore when next phase starts

### Production Environment

**⚠️ Never stop or destroy production!**
- Use Multi-AZ for high availability
- Enable automated backups (7-30 days retention)
- Use snapshots for disaster recovery

---

## Cost Optimization Best Practices

### 1. Use Reserved Instances for Production

For production (running 24/7), purchase Reserved Instances:
- **1-year commitment:** ~40% savings
- **3-year commitment:** ~60% savings

```bash
# Example: Purchase RDS Reserved Instance
aws rds purchase-reserved-db-instances-offering \
  --reserved-db-instances-offering-id <offering-id> \
  --reserved-db-instance-id drive-ops-prod-reservation
```

### 2. Right-Size Instances

Monitor and adjust instance sizes based on usage:

**Check RDS metrics:**
```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/RDS \
  --metric-name CPUUtilization \
  --dimensions Name=DBInstanceIdentifier,Value=drive-ops-dev-postgres \
  --start-time $(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 3600 \
  --statistics Average
```

**If CPU < 20% consistently:** Downgrade instance class

### 3. Clean Up Unused Resources

**Delete old snapshots:**
```bash
# List snapshots older than 30 days
aws rds describe-db-snapshots \
  --query "DBSnapshots[?SnapshotCreateTime<='$(date -u -d '30 days ago' +%Y-%m-%d)'].DBSnapshotIdentifier" \
  --output text

# Delete old snapshots
aws rds delete-db-snapshot --db-snapshot-identifier <snapshot-id>
```

**Delete unused EBS volumes:**
```bash
# List unattached volumes
aws ec2 describe-volumes \
  --filters Name=status,Values=available \
  --query 'Volumes[*].[VolumeId,Size,CreateTime]' \
  --output table

# Delete unused volume
aws ec2 delete-volume --volume-id vol-xyz
```

### 4. Use Spot Instances for Non-Critical Workloads

For dev/testing EC2 instances, use Spot Instances (up to 90% savings):

```hcl
# terraform/modules/ec2/main.tf
resource "aws_instance" "dev" {
  instance_type = "t3.micro"

  # Enable spot instances for dev
  instance_market_options {
    market_type = "spot"
    spot_options {
      max_price          = "0.01"  # ~70% discount
      spot_instance_type = "persistent"
    }
  }
}
```

---

## Monitoring and Alerts

### Cost Alerts

**Create budget alert:**
```bash
aws budgets create-budget \
  --account-id ACCOUNT_ID \
  --budget file://budget.json \
  --notifications-with-subscribers file://notifications.json
```

**budget.json:**
```json
{
  "BudgetName": "drive-ops-monthly-budget",
  "BudgetLimit": {
    "Amount": "50",
    "Unit": "USD"
  },
  "TimeUnit": "MONTHLY",
  "BudgetType": "COST"
}
```

**notifications.json:**
```json
[
  {
    "Notification": {
      "NotificationType": "ACTUAL",
      "ComparisonOperator": "GREATER_THAN",
      "Threshold": 80
    },
    "Subscribers": [
      {
        "SubscriptionType": "EMAIL",
        "Address": "devops@company.com"
      }
    ]
  }
]
```

### Usage Monitoring

**Daily cost report:**
```bash
# Get yesterday's cost
aws ce get-cost-and-usage \
  --time-period Start=$(date -u -d '1 day ago' +%Y-%m-%d),End=$(date -u +%Y-%m-%d) \
  --granularity DAILY \
  --metrics BlendedCost \
  --group-by Type=SERVICE
```

---

## Quick Reference Commands

### Daily Operations
```bash
# Stop dev environment (end of day)
aws rds stop-db-instance --db-instance-identifier drive-ops-dev-postgres
aws ec2 stop-instances --instance-ids i-xxx i-yyy i-zzz

# Start dev environment (morning)
aws rds start-db-instance --db-instance-identifier drive-ops-dev-postgres
aws ec2 start-instances --instance-ids i-xxx i-yyy i-zzz
```

### Weekend Shutdown
```bash
# Friday evening
./scripts/stop-dev-environment.sh

# Monday morning
./scripts/start-dev-environment.sh
```

### Emergency Cost Reduction
```bash
# Stop everything immediately
terragrunt run-all destroy --terragrunt-working-dir infra/terragrunt/envs/dev
```

---

## Scripts

**Create helper scripts** in `infra/scripts/`:

**`stop-dev-environment.sh`:**
```bash
#!/bin/bash
set -e

echo "🛑 Stopping dev environment..."

# Stop RDS
aws rds stop-db-instance \
  --db-instance-identifier drive-ops-dev-postgres || true

# Stop EC2 instances
aws ec2 stop-instances \
  --instance-ids \
    i-client-gateway-id \
    i-trip-service-id \
    i-driver-service-id

echo "✅ Dev environment stopped. Estimated savings: $5/day"
```

**`start-dev-environment.sh`:**
```bash
#!/bin/bash
set -e

echo "🚀 Starting dev environment..."

# Start RDS
aws rds start-db-instance \
  --db-instance-identifier drive-ops-dev-postgres

# Wait for RDS to be available
aws rds wait db-instance-available \
  --db-instance-identifier drive-ops-dev-postgres

# Start EC2 instances
aws ec2 start-instances \
  --instance-ids \
    i-client-gateway-id \
    i-trip-service-id \
    i-driver-service-id

# Wait for instances to be running
aws ec2 wait instance-running \
  --instance-ids \
    i-client-gateway-id \
    i-trip-service-id \
    i-driver-service-id

echo "✅ Dev environment started and ready"
```

---

## Next Steps

1. ✅ Implement automated RDS scheduler Lambda for dev environment
2. ✅ Create helper scripts for manual stop/start operations
3. ✅ Set up AWS Budgets and cost alerts
4. ✅ Document snapshot/restore procedures in runbook
5. ✅ Test full destroy/recreate flow in staging
6. ✅ Train team on cost control best practices
