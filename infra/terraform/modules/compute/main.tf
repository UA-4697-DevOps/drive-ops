resource "aws_instance" "this" {
  ami                         = local.resolved_ami
  instance_type               = var.instance_type
  subnet_id                   = var.subnet_id
  vpc_security_group_ids      = concat([aws_security_group.ec2.id], var.additional_security_group_ids)
  key_name                    = var.key_name
  associate_public_ip_address = var.associate_public_ip_address
  iam_instance_profile        = aws_iam_instance_profile.ec2_profile.name
  monitoring                  = var.enable_monitoring
  user_data                   = local.resolved_user_data
  disable_api_termination     = var.enable_termination_protection

  root_block_device {
    volume_size           = var.root_volume_size
    volume_type           = var.root_volume_type
    delete_on_termination = true
    encrypted             = true

    tags = merge(var.tags, {
      Name = "${var.name}-root-volume"
    })
  }

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
    instance_metadata_tags      = "enabled"
  }

  tags = merge(var.tags, {
    Name = var.name
  })

  # --- CRITICAL UPDATE ---
  lifecycle {
    ignore_changes = [
      ami,
      # REMOVED user_data from here. 
      # This allows Terraform to detect the new SSM Agent installation 
      # script and replace the instance.
    ]
  }
}
