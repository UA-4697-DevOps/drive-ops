output "instance_id" {
  description = "EC2 instance ID"
  value       = aws_instance.docker_host.id
}

output "instance_public_ip" {
  description = "EC2 instance public IP"
  value       = aws_instance.docker_host.public_ip
}

output "instance_private_ip" {
  description = "EC2 instance private IP"
  value       = aws_instance.docker_host.private_ip
}

output "ssm_document_name" {
  description = "SSM document name for deployment"
  value       = aws_ssm_document.deploy_service.name
}

output "iam_role_arn" {
  description = "IAM role ARN for EC2"
  value       = aws_iam_role.ec2_ssm_role.arn
}
