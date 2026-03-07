output "nat_instance_id" {
  description = "Instance ID of the NAT instance. null when enabled = false."
  value       = try(aws_instance.nat_instance[0].id, null)
}

output "nat_instance_public_ip" {
  description = "Elastic IP address assigned to the NAT instance. null when enabled = false."
  value       = try(aws_eip.nat_instance[0].public_ip, null)
}

output "nat_instance_private_ip" {
  description = "Private IP address of the NAT instance within the VPC. null when enabled = false."
  value       = try(aws_instance.nat_instance[0].private_ip, null)
}

output "nat_security_group_id" {
  description = "Security group ID of the NAT instance. null when enabled = false."
  value       = try(aws_security_group.nat_instance[0].id, null)
}
