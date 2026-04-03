output "bastion_public_ip" {
  description = "Elastic IP address of the bastion host"
  value       = aws_eip.bastion.public_ip
}

output "bastion_instance_id" {
  description = "Instance ID of the bastion host"
  value       = aws_instance.bastion.id
}

output "bastion_security_group_id" {
  description = "Security group ID of the bastion host"
  value       = module.security_group.sg_id
}

output "bastion_role_arn" {
  description = "ARN of the bastion IAM role (used for EKS access entries)"
  value       = aws_iam_role.bastion.arn
}
