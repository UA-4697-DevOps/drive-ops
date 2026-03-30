# ==============================================================================
# EC2 INSTANCE MODULE
# ==============================================================================
# A reusable, hardened EC2 instance with sensible defaults:
#   - IMDSv2 enforced (http_tokens = "required")
#   - Encrypted gp3 root volume
#   - Lifecycle: ignore AMI drift (prevents accidental replacement)
#
# This module owns ONLY the aws_instance resource. IAM roles, security groups,
# EIPs, and user_data scripts are the responsibility of the calling module.
# ==============================================================================

resource "aws_instance" "this" {
  ami                         = var.ami
  instance_type               = var.instance_type
  subnet_id                   = var.subnet_id
  vpc_security_group_ids      = var.vpc_security_group_ids
  key_name                    = var.key_name
  iam_instance_profile        = var.iam_instance_profile
  monitoring                  = var.monitoring
  associate_public_ip_address = var.associate_public_ip_address
  user_data                   = var.user_data
  disable_api_termination     = var.disable_api_termination
  source_dest_check           = var.source_dest_check

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required" # IMDSv2 only
    http_put_response_hop_limit = var.metadata_hop_limit
    instance_metadata_tags      = var.instance_metadata_tags ? "enabled" : "disabled"
  }

  root_block_device {
    volume_size           = var.root_volume_size
    volume_type           = var.root_volume_type
    iops                  = var.root_volume_iops
    throughput            = var.root_volume_type == "gp3" ? var.root_volume_throughput : null
    encrypted             = true # always encrypted
    kms_key_id            = var.root_volume_kms_key_id
    delete_on_termination = true

    tags = merge(var.tags, {
      Name = "${var.name}-root-volume"
    })
  }

  tags = merge(var.tags, var.extra_tags, {
    Name = var.name
  })

  lifecycle {
    ignore_changes = [ami]

    precondition {
      condition     = contains(["io1", "io2"], var.root_volume_type) ? var.root_volume_iops != null : true
      error_message = "root_volume_iops must be provided when root_volume_type is io1 or io2."
    }

    precondition {
      condition     = var.root_volume_throughput != null ? var.root_volume_type == "gp3" : true
      error_message = "root_volume_throughput is only valid when root_volume_type is gp3."
    }
  }
}
