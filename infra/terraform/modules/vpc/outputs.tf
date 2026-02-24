output "vpc_id" {
  description = "The ID of the VPC"
  value       = aws_vpc.main.id
}

output "vpc_cidr" {
  description = "The CIDR block of the VPC"
  value       = aws_vpc.main.cidr_block
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

output "nat_instance_id" {
  description = "The ID of the NAT Instance (null if disabled)"
  value       = var.use_nat_instance ? aws_instance.nat_instance[0].id : null
}

output "nat_instance_public_ip" {
  description = "The public IP address of the NAT Instance (null if disabled)"
  value       = var.use_nat_instance ? aws_eip.nat_instance[0].public_ip : null
}

output "nat_instance_private_ip" {
  description = "The private IP address of the NAT Instance (null if disabled)"
  value       = var.use_nat_instance ? aws_instance.nat_instance[0].private_ip : null
}
