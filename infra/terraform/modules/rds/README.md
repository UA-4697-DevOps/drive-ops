# RDS PostgreSQL Module

Terraform module for creating AWS RDS PostgreSQL instances with secure defaults.

## Features

- ✅ PostgreSQL 15.x with encryption at rest
- ✅ Automated backups and maintenance windows
- ✅ Multi-AZ support for high availability
- ✅ VPC subnet group for network isolation
- ✅ Security group integration
- ✅ Secure password generation
- ✅ Performance Insights (optional)

## Security

### Password Management

**IMPORTANT**: This module does NOT expose the master password by default for security reasons.

#### Why the password is not in outputs:

- ❌ Terraform state files can be accessed by multiple users
- ❌ CI/CD logs may capture terraform outputs
- ❌ Console output can leak through screenshots
- ❌ Violates principle of least privilege

#### How to access the password:

**For Applications (RECOMMENDED):**
```typescript
// Use AWS Secrets Manager (when implemented)
import { SecretsManagerClient, GetSecretValueCommand } from "@aws-sdk/client-secrets-manager";

const client = new SecretsManagerClient({ region: "us-east-2" });
const response = await client.send(
  new GetSecretValueCommand({ SecretId: "drive-ops/dev/rds/credentials" })
);
const credentials = JSON.parse(response.SecretString);
```

**For Local Debugging Only:**
```hcl
# In terragrunt.hcl or terraform.tfvars
inputs = {
  expose_master_password = true  # NEVER set this in production!
}
```

Then retrieve:
```bash
terragrunt output db_master_password
```

**For Emergency Access:**
- Use AWS Console → RDS → Modify → New Password
- Or use AWS CLI: `aws rds modify-db-instance`

## Usage

### Basic Example

```hcl
module "rds" {
  source = "../../../../terraform/modules/rds"

  project_name = "drive-ops"
  env          = "dev"
  db_name      = "drive_ops_dev"

  # Network (from VPC module)
  vpc_id               = module.vpc.vpc_id
  private_subnet_ids   = module.vpc.private_subnet_ids
  db_security_group_id = module.vpc.sg_db_id

  # Instance configuration
  instance_class          = "db.t3.micro"
  allocated_storage       = 20
  engine_version          = "15.8"

  # Backups
  backup_retention_period = 1

  # HA (disable for dev to save costs)
  multi_az = false

  # Protection
  deletion_protection = false
  skip_final_snapshot = true
}
```

### Production Example

```hcl
module "rds" {
  source = "../../../../terraform/modules/rds"

  project_name = "drive-ops"
  env          = "prod"
  db_name      = "drive_ops_prod"

  # Network
  vpc_id               = module.vpc.vpc_id
  private_subnet_ids   = module.vpc.private_subnet_ids
  db_security_group_id = module.vpc.sg_db_id

  # Larger instance for production
  instance_class          = "db.t3.medium"
  allocated_storage       = 100
  engine_version          = "15.8"

  # Longer backup retention
  backup_retention_period = 30

  # Enable HA
  multi_az = true

  # Enable protection
  deletion_protection = true
  skip_final_snapshot = false

  # Enable Performance Insights with customer-managed KMS key (required for CKV_AWS_354)
  enable_performance_insights           = true
  performance_insights_kms_key_id       = module.kms.rds_pi_kms_key_arn  # From KMS module
  performance_insights_retention_period = 731  # Long-term retention for prod
}
```

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|----------|
| project_name | Project name for resource naming | string | - | yes |
| env | Environment (dev/staging/prod) | string | - | yes |
| db_name | Database name | string | - | yes |
| vpc_id | VPC ID | string | - | yes |
| private_subnet_ids | List of private subnet IDs | list(string) | - | yes |
| db_security_group_id | Security group ID for database | string | - | yes |
| master_username | Master username | string | "postgres" | no |
| engine_version | PostgreSQL version | string | "15.8" | no |
| instance_class | Instance type | string | "db.t3.micro" | no |
| allocated_storage | Storage size in GB | number | 20 | no |
| backup_retention_period | Backup retention days | number | 1 | no |
| multi_az | Enable Multi-AZ | bool | false | no |
| deletion_protection | Enable deletion protection | bool | false | no |
| skip_final_snapshot | Skip final snapshot | bool | true | no |
| enable_performance_insights | Enable Performance Insights | bool | false | no |
| performance_insights_kms_key_id | KMS key ARN for PI encryption (required if PI enabled) | string | null | no |
| performance_insights_retention_period | PI data retention (7 or 731 days) | number | 7 | no |

## Outputs

| Name | Description |
|------|-------------|
| db_endpoint | Connection endpoint (host:port) |
| db_address | Hostname only |
| db_port | Port number (5432) |
| db_name | Database name |
| db_instance_id | RDS instance identifier |
| db_instance_arn | RDS instance ARN |
| db_subnet_group_name | DB subnet group name |
| db_connection_info | Object with all connection details |
| connection_string | PostgreSQL connection string (without password) |
| performance_insights_enabled | Whether Performance Insights is enabled |
| performance_insights_kms_key_id | KMS key ARN for PI (null if disabled) |
| performance_insights_retention_period | PI retention period (null if disabled) |

## Cost Optimization

### Dev Environment
- Use `db.t3.micro` instance ($13-15/month)
- Set `multi_az = false`
- Set `backup_retention_period = 1`
- Enable manual stop: `aws rds stop-db-instance --db-instance-identifier <name>`

### Stop/Start Commands
```bash
# Stop RDS (saves ~50% cost, max 7 days)
aws rds stop-db-instance --db-instance-identifier drive-ops-dev-postgres

# Start RDS
aws rds start-db-instance --db-instance-identifier drive-ops-dev-postgres
```

## Maintenance

### Backup Windows
- Automated backups: 03:00-04:00 UTC
- Maintenance window: Monday 04:00-05:00 UTC

### Manual Snapshot
```bash
aws rds create-db-snapshot \
  --db-instance-identifier drive-ops-dev-postgres \
  --db-snapshot-identifier manual-backup-$(date +%Y%m%d)
```

### Restore from Snapshot
```bash
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier drive-ops-dev-postgres-restored \
  --db-snapshot-identifier manual-backup-20260129
```

## Troubleshooting

### Cannot connect to database
1. Check security group allows access from application SG
2. Verify database is in `available` state
3. Check VPC subnet group configuration
4. Verify applications are in same VPC

### Password not in outputs
This is intentional for security. See "Password Management" section above.

### Database is too slow
1. Enable Performance Insights (see section below)
2. Check CloudWatch metrics
3. Consider upgrading instance class
4. Review query performance

## Performance Insights Setup

### Security Requirement (CKV_AWS_354)

Performance Insights **MUST** use a customer-managed KMS key (CMK) for encryption. AWS-managed keys are not compliant.

### Step 1: Create KMS Key for Performance Insights

Create a separate KMS key module or add to your secrets module:

```hcl
# terraform/modules/kms/main.tf (or add to secrets module)
resource "aws_kms_key" "rds_performance_insights" {
  description             = "KMS key for RDS Performance Insights encryption"
  deletion_window_in_days = 10
  enable_key_rotation     = true

  tags = {
    Name = "${var.project_name}-${var.env}-rds-pi-kms"
  }
}

resource "aws_kms_alias" "rds_performance_insights" {
  name          = "alias/${var.project_name}-${var.env}-rds-pi"
  target_key_id = aws_kms_key.rds_performance_insights.key_id
}

output "rds_pi_kms_key_arn" {
  description = "ARN of KMS key for RDS Performance Insights"
  value       = aws_kms_key.rds_performance_insights.arn
}
```

### Step 2: Use in RDS Module

```hcl
# terragrunt/envs/prod/rds/terragrunt.hcl
dependency "kms" {
  config_path = "../kms"  # or "../secrets" if KMS is there
}

inputs = {
  # ... other inputs ...

  # Enable Performance Insights with CMK
  enable_performance_insights        = true
  performance_insights_kms_key_id    = dependency.kms.outputs.rds_pi_kms_key_arn
  performance_insights_retention_period = 7  # or 731 for long-term retention
}
```

### What Happens Without CMK?

If you try to enable Performance Insights without providing a KMS key:

```
Error: SECURITY REQUIREMENT (CKV_AWS_354): When enable_performance_insights is true,
performance_insights_kms_key_id must be provided with a customer-managed KMS key ARN.
Performance Insights data must be encrypted with a CMK for compliance.
```

### Cost Considerations

- **Performance Insights**: ~$0.18/vCPU/month
- **KMS Key**: $1/month + $0.03 per 10,000 requests
- **7-day retention**: Free tier
- **731-day retention**: Additional cost

### Best Practices

1. **Create separate KMS key** for Performance Insights (not shared with storage encryption)
2. **Enable key rotation** for the KMS key
3. **Use 7-day retention** for dev, 731-day for production troubleshooting
4. **Monitor KMS costs** if PI generates many encryption requests

## References

- [AWS RDS PostgreSQL Documentation](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_PostgreSQL.html)
- [RDS Best Practices](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_BestPractices.html)
- [Terraform aws_db_instance](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/db_instance)
