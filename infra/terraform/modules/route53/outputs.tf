# ==============================================================================
# ROUTE53 MODULE – OUTPUTS
# ==============================================================================

output "zone_id" {
  description = "The hosted zone ID"
  value       = aws_route53_zone.main.zone_id
}

output "zone_name" {
  description = "The hosted zone name"
  value       = aws_route53_zone.main.name
}

output "name_servers" {
  description = "The name servers for the hosted zone (configure these at your domain registrar)"
  value       = aws_route53_zone.main.name_servers
}
