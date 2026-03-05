output "s3_bucket_name" {
  description = "Name of the S3 bucket for Terraform state"
  value       = module.state_backend.s3_bucket_id
}

output "dynamodb_table_name" {
  description = "Name of the DynamoDB table for state locking"
  value       = module.state_backend.dynamodb_table_name
}

output "eso_role_arn" {
  description = "ARN of the IAM role for External Secrets Operator"
  value       = module.external_secrets.eso_role_arn
}
