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
