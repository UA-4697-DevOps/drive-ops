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

output "private_route_table_id" {
  description = "ID of the private subnet route table (used by the NAT module to add a default route)"
  value       = aws_route_table.private.id
}

output "private_subnet_cidrs" {
  description = "CIDR blocks of all private subnets (used by the NAT module SG ingress)"
  value       = aws_subnet.private[*].cidr_block
}

output "sg_alb_id" {
  description = "The ID of the security group for Application Load Balancer"
  value       = aws_security_group.alb.id
}
