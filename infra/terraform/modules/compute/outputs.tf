output "instance_id" {
  description = "ID of the EC2 instance"
  value       = aws_instance.this.id
}

output "instance_public_ip" {
  description = "Public IP address of the EC2 instance"
  value       = aws_instance.this.public_ip
}

output "instance_private_ip" {
  description = "Private IP address of the EC2 instance"
  value       = aws_instance.this.private_ip
}

output "security_group_id" {
  description = "ID of the EC2 security group"
  value       = module.security_group.sg_id
}

output "iam_role_arn" {
  description = "ARN of the EC2 IAM role"
  value       = module.ec2_iam_role.iam_role_arn
}

output "instance_profile_name" {
  description = "Name of the EC2 IAM instance profile"
  value       = module.ec2_iam_role.iam_instance_profile_name
}
