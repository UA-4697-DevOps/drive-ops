output "rds_master_password" {
  description = "RDS master password (sensitive)"
  value       = random_password.master_password.result
  sensitive   = true
}
