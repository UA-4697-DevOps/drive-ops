output "bastion_public_ip" {
  description = "Elastic IP address of the bastion host"
  value       = aws_eip.bastion.public_ip
}

output "bastion_instance_id" {
  description = "Instance ID of the bastion host"
  value       = aws_instance.bastion.id
}

output "bastion_security_group_id" {
  description = "Security group ID of the bastion host"
  value       = aws_security_group.bastion.id
}

output "vpn_client_config_secret_name" {
  description = "Secrets Manager secret name for the OpenVPN client .ovpn profile. Retrieve with: aws secretsmanager get-secret-value --secret-id <name> --query SecretString --output text > client1.ovpn"
  value       = var.enable_openvpn ? "${var.project_name}/${var.env}/openvpn/clients/client1" : null
}
