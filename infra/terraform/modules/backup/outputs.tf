output "s3_bucket_id" {
  description = "The name of the S3 bucket created for backups"
  value       = aws_s3_bucket.db_backups.id
}

output "backup_iam_role_arn" {
  description = "The ARN of the IAM role to attach to the Kubernetes Service Account"
  value       = aws_iam_role.backup_role.arn
}
