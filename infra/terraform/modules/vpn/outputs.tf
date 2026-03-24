output "vpn_public_ip" {
  description = "Elastic IP address of the VPN server — this is the remote endpoint in client .ovpn profiles"
  value       = aws_eip.vpn.public_ip
}

output "vpn_instance_id" {
  description = "Instance ID of the VPN EC2 instance"
  value       = aws_instance.vpn.id
}

output "vpn_security_group_id" {
  description = "Security group ID of the VPN instance"
  value       = module.security_group.sg_id
}

output "vpn_client_config_secret_name" {
  description = "Secrets Manager secret name for the OpenVPN client .ovpn profile. Retrieve with: aws secretsmanager get-secret-value --secret-id <name> --query SecretString --output text > client1.ovpn"
  value       = "${var.project_name}/${var.env}/openvpn/clients/client1"
}
