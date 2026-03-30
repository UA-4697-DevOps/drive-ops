output "bastion_public_ip" {
  description = "Elastic IP address of the bastion host"
  value       = module.ec2.eip_public_ip
}

output "bastion_instance_id" {
  description = "Instance ID of the bastion host"
  value       = module.ec2.instance_id
}

output "bastion_security_group_id" {
  description = "Security group ID of the bastion host"
  value       = module.security_group.sg_id
}
