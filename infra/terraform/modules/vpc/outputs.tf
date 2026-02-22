output "vpc_id" {
  description = "The ID of the VPC"
  value       = aws_vpc.main.id
}

output "public_subnet_ids" {
  description = "List of IDs of public subnets"
  value       = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  description = "List of IDs of private subnets"
  value       = aws_subnet.private[*].id
}

output "sg_app_id" {
  description = "The ID of the security group for application services"
  value       = aws_security_group.app.id
}

output "sg_db_id" {
  description = "The ID of the security group for database workloads"
  value       = aws_security_group.db.id
}

output "nat_gateway_id" {
  description = "The ID of the NAT Gateway (null if disabled)"
  value       = var.enable_nat_gateway ? aws_nat_gateway.nat[0].id : null
}

output "nat_gateway_public_ip" {
  description = "The public IP address of the NAT Gateway (null if disabled)"
  value       = var.enable_nat_gateway ? aws_eip.nat[0].public_ip : null
}
