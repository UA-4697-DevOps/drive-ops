# ==============================================================================
# EC2 INSTANCE MODULE – OUTPUTS
# ==============================================================================

output "instance_id" {
  description = "ID of the EC2 instance"
  value       = aws_instance.this.id
}

output "public_ip" {
  description = "Public IP address of the EC2 instance (null if no public IP)"
  value       = aws_instance.this.public_ip
}

output "private_ip" {
  description = "Private IP address of the EC2 instance"
  value       = aws_instance.this.private_ip
}

output "primary_network_interface_id" {
  description = "ID of the primary network interface (useful for NAT route targets)"
  value       = aws_instance.this.primary_network_interface_id
}

output "arn" {
  description = "ARN of the EC2 instance"
  value       = aws_instance.this.arn
}

output "eip_public_ip" {
  description = "Elastic IP address (null if create_eip = false)"
  value       = var.create_eip ? aws_eip.this[0].public_ip : null
}

output "eip_allocation_id" {
  description = "Allocation ID of the Elastic IP (null if create_eip = false)"
  value       = var.create_eip ? aws_eip.this[0].id : null
}
