output "nat_instance_id" {
  description = "Instance ID of the NAT instance. null when enabled = false."
  value       = try(module.ec2[0].instance_id, null)
}

output "nat_instance_public_ip" {
  description = "Elastic IP address assigned to the NAT instance. null when enabled = false."
  value       = try(module.ec2[0].eip_public_ip, null)
}

output "nat_instance_private_ip" {
  description = "Private IP address of the NAT instance within the VPC. null when enabled = false."
  value       = try(module.ec2[0].private_ip, null)
}

output "nat_security_group_id" {
  description = "Security group ID of the NAT instance. null when enabled = false."
  value       = try(module.security_group[0].sg_id, null)
}
