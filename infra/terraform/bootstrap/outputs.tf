output "s3_bucket_name" {
  description = "Name of the S3 bucket for Terraform state"
  value       = module.state_backend.s3_bucket_id
}

output "dynamodb_table_name" {
  description = "Name of the DynamoDB table for state locking"
  value       = module.state_backend.dynamodb_table_name
}
