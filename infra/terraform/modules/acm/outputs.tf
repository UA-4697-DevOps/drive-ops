# ==============================================================================
# ACM MODULE – OUTPUTS
# ==============================================================================

output "certificate_arn" {
  description = "The ARN of the validated certificate"
  value       = aws_acm_certificate_validation.wildcard.certificate_arn
}

output "certificate_id" {
  description = "The ID of the certificate"
  value       = aws_acm_certificate.wildcard.id
}

output "certificate_domain_name" {
  description = "The domain name the certificate is for"
  value       = aws_acm_certificate.wildcard.domain_name
}

output "certificate_status" {
  description = "The validation status of the certificate"
  value       = aws_acm_certificate.wildcard.status
}
