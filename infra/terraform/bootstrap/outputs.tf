output "s3_bucket_name" {
  description = "Name of the S3 bucket for Terraform state"
  value       = module.state_backend.s3_bucket_id
}

output "dynamodb_table_name" {
  description = "Name of the DynamoDB table for state locking"
  value       = module.state_backend.dynamodb_table_name
}

output "backend_config" {
  description = "Backend configuration for other Terraform modules"
  value       = <<-EOT
    Backend configuration created successfully!

    S3 Bucket: ${module.state_backend.s3_bucket_id}
    DynamoDB Table: ${module.state_backend.dynamodb_table_name}
    Region: ${var.aws_region}

    You can now use Terragrunt with remote state.
  EOT
}
