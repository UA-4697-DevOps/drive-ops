# ==============================================================================
# EKS MODULE – CLUSTER & NODE GROUP
# ==============================================================================
# Creates:
#   1. Security group for the EKS cluster (control-plane ↔ node communication)
#   2. EKS cluster (managed control plane)
#   3. CloudWatch log group for control-plane logs
#   4. Managed node group with autoscaling
#
# IMPORTANT – CGROUP V2 SUPPORT (Kubernetes v1.35+):
#   Kubernetes v1.35 disables cgroup v1 by default (step toward deprecation). The default node AMI (AL2023) uses
#   cgroup v2 natively. For custom AMIs or edge cases, set `kubelet_extra_args`
#   variable to "--fail-cgroupv1=false" (note the correct flag spelling) to enable cgroup v1 fallback if needed.
#   Alternatively, set `failCgroupV1: false` in the KubeletConfiguration (kube-system/kubelet-config) for clusters using nodeadm.
#   For EKS managed node groups with AL2023/nodeadm, apply this via a nodeadm KubeletConfiguration overlay (not by injecting a raw kubelet CLI flag via user_data.sh).
#   Use `kubelet_extra_args` only for non-nodeadm/custom AMI cases. Preferred approach: migrate all nodes to cgroup v2 or use AL2023 (default).
# ==============================================================================

# NOTE: Locals are defined in data.tf (cluster_name, node_group_name, etc.)

# ------------------------------------------------------------------------------
# 1. EKS CLUSTER SECURITY GROUP
# ------------------------------------------------------------------------------

resource "aws_security_group" "eks_cluster" {
  name        = "${local.cluster_name}-cluster-sg"
  description = "Security group for EKS cluster control plane"
  vpc_id      = var.vpc_id

  tags = merge(var.tags, {
    Name = "${local.cluster_name}-cluster-sg"
  })
}

# Allow unrestricted egress from cluster to reach AWS services and external APIs.
# Nodes are in private subnets; outbound traffic routes through the NAT Instance.
resource "aws_security_group_rule" "cluster_egress" {
  type              = "egress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.eks_cluster.id
  description       = "Allow all outbound traffic from control plane"
}

# Allow worker nodes to communicate with the cluster API
resource "aws_security_group_rule" "cluster_ingress_nodes" {
  type                     = "ingress"
  from_port                = 443
  to_port                  = 443
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.eks_nodes.id
  security_group_id        = aws_security_group.eks_cluster.id
  description              = "Allow worker nodes to reach the API server"
}

# ------------------------------------------------------------------------------
# 2. NODE SECURITY GROUP
# ------------------------------------------------------------------------------

resource "aws_security_group" "eks_nodes" {
  name        = "${local.cluster_name}-node-sg"
  description = "Security group for EKS worker nodes"
  vpc_id      = var.vpc_id

  tags = merge(var.tags, {
    Name = "${local.cluster_name}-node-sg"
  })
}

# Allow unrestricted egress from nodes to reach AWS services, container registries, and external APIs.
# Nodes are in private subnets; outbound traffic routes through the NAT Instance.
resource "aws_security_group_rule" "nodes_egress" {
  type              = "egress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.eks_nodes.id
  description       = "Allow all outbound traffic from worker nodes"
}

resource "aws_security_group_rule" "nodes_internal" {
  type                     = "ingress"
  from_port                = 0
  to_port                  = 0
  protocol                 = "-1"
  source_security_group_id = aws_security_group.eks_nodes.id
  security_group_id        = aws_security_group.eks_nodes.id
  description              = "Allow node-to-node communication (all protocols including UDP and ICMP for CoreDNS and PMTU)"
}

resource "aws_security_group_rule" "nodes_ingress_cluster" {
  type                     = "ingress"
  from_port                = 1025
  to_port                  = 65535
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.eks_cluster.id
  security_group_id        = aws_security_group.eks_nodes.id
  description              = "Allow control plane to reach worker nodes (kubelet, kube-proxy)"
}

resource "aws_security_group_rule" "nodes_ingress_cluster_443" {
  type                     = "ingress"
  from_port                = 443
  to_port                  = 443
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.eks_cluster.id
  security_group_id        = aws_security_group.eks_nodes.id
  description              = "Allow control plane to reach webhook endpoints on nodes"
}

# Allow the bastion host to SSH into worker nodes for debugging.
# Only created when bastion_sg_id is provided; omit to rely solely on SSM.
resource "aws_security_group_rule" "nodes_ingress_bastion_ssh" {
  count                    = var.bastion_sg_id != null ? 1 : 0
  type                     = "ingress"
  from_port                = 22
  to_port                  = 22
  protocol                 = "tcp"
  source_security_group_id = var.bastion_sg_id
  security_group_id        = aws_security_group.eks_nodes.id
  description              = "SSH from bastion host to worker nodes"
}

# ------------------------------------------------------------------------------
# 3. CLOUDWATCH LOG GROUP (CONTROL PLANE LOGS)
# ------------------------------------------------------------------------------

resource "aws_cloudwatch_log_group" "eks" {
  name              = "/aws/eks/${local.cluster_name}/cluster"
  retention_in_days = var.cluster_log_retention_in_days
  kms_key_id        = var.kms_key_arn
  tags              = var.tags
}

# ------------------------------------------------------------------------------
# 4. EKS CLUSTER
# ------------------------------------------------------------------------------

resource "aws_eks_cluster" "this" {
  name     = local.cluster_name
  version  = var.cluster_version
  role_arn = aws_iam_role.eks_cluster.arn

  # Validation: prevent unintentional public API exposure
  lifecycle {
    precondition {
      condition     = !var.cluster_endpoint_public_access || length(var.cluster_endpoint_public_access_cidrs) > 0
      error_message = "cluster_endpoint_public_access_cidrs must not be empty when cluster_endpoint_public_access is true. Providing an empty CIDR list would expose the EKS API to the internet (AWS treats empty as 0.0.0.0/0). Either set cluster_endpoint_public_access to false or provide specific CIDR blocks."
    }
  }

  # API endpoint: private-only access (cluster_endpoint_public_access = false)
  # Use bastion SSH or OpenVPN tunnel to reach kubectl.
  vpc_config {
    subnet_ids              = local.cluster_subnet_ids
    security_group_ids      = [aws_security_group.eks_cluster.id]
    endpoint_public_access  = var.cluster_endpoint_public_access
    endpoint_private_access = var.cluster_endpoint_private_access
    public_access_cidrs     = var.cluster_endpoint_public_access_cidrs
  }

  # Envelope encryption for Kubernetes secrets (only when a CMK ARN is supplied)
  dynamic "encryption_config" {
    for_each = var.kms_key_arn != null ? [var.kms_key_arn] : []
    content {
      provider {
        key_arn = encryption_config.value
      }
      resources = ["secrets"]
    }
  }

  enabled_cluster_log_types = var.enabled_cluster_log_types

  tags = merge(var.tags, {
    Name = local.cluster_name
  })

  # Ensure IAM roles and log group are created before the cluster
  depends_on = [
    aws_iam_role_policy_attachment.eks_cluster_policy,
    aws_iam_role_policy_attachment.eks_vpc_resource_controller,
    aws_cloudwatch_log_group.eks,
  ]
}

# ------------------------------------------------------------------------------
# 5. NODE LAUNCH TEMPLATE
# ------------------------------------------------------------------------------

resource "aws_launch_template" "eks_nodes" {
  name_prefix = "${local.node_group_name}-lt-"

  network_interfaces {
    associate_public_ip_address = var.node_associate_public_ip_address
    security_groups             = [aws_security_group.eks_nodes.id]
    delete_on_termination       = true
  }

  block_device_mappings {
    device_name = contains([
      "BOTTLEROCKET_x86_64",
      "BOTTLEROCKET_ARM_64",
      "BOTTLEROCKET_x86_64_NVIDIA",
      "BOTTLEROCKET_ARM_64_NVIDIA",
      "BOTTLEROCKET_ARM_64_FIPS",
      "BOTTLEROCKET_x86_64_FIPS",
      "BOTTLEROCKET_ARM_64_NVIDIA_FIPS",
      "BOTTLEROCKET_x86_64_NVIDIA_FIPS"
    ], var.node_ami_type) ? "/dev/xvdb" : "/dev/xvda"
    ebs {
      volume_size           = var.node_disk_size
      volume_type           = "gp3"
      delete_on_termination = true
      encrypted             = true
      kms_key_id            = var.kms_key_arn
    }
  }

  # IMDSv2 required; IRSA uses projected service account tokens, not instance IMDS.
  # Reducing hop_limit to 1 prevents pods from reaching instance IMDS (Checkov CKV_AWS_341).
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }

  # Optional kubelet extra arguments (e.g., for cgroup v1 fallback on custom AMIs)
  user_data = var.kubelet_extra_args != null && var.kubelet_extra_args != "" ? base64encode(templatefile("${path.module}/user_data.sh", {
    kubelet_extra_args = replace(replace(var.kubelet_extra_args, "\"", "\\\""), "\n", "\\n")
  })) : null

  tag_specifications {
    resource_type = "instance"
    tags          = merge(var.tags, { Name = local.node_group_name })
  }

  tag_specifications {
    resource_type = "volume"
    tags          = merge(var.tags, { Name = local.node_group_name })
  }

  tags = var.tags

  lifecycle {
    precondition {
      condition     = !(startswith(var.node_ami_type, "BOTTLEROCKET_") && var.kubelet_extra_args != "")
      error_message = "kubelet_extra_args via user_data.sh is not supported for Bottlerocket AMI types. Use a TOML-format nodeadm overlay or a custom Bottlerocket user-data template instead."
    }
    create_before_destroy = true
  }
}

# ------------------------------------------------------------------------------
# 6. MANAGED NODE GROUP
# ------------------------------------------------------------------------------

resource "aws_eks_node_group" "default" {
  cluster_name    = aws_eks_cluster.this.name
  node_group_name = local.node_group_name
  node_role_arn   = aws_iam_role.node_group.arn
  subnet_ids      = local.resolved_node_subnet_ids

  instance_types = var.node_instance_types
  ami_type       = var.node_ami_type
  capacity_type  = var.node_capacity_type
  # disk_size is managed by the launch template block_device_mappings

  launch_template {
    id      = aws_launch_template.eks_nodes.id
    version = aws_launch_template.eks_nodes.latest_version
  }

  scaling_config {
    desired_size = var.node_desired_size
    min_size     = var.node_min_size
    max_size     = var.node_max_size
  }

  update_config {
    max_unavailable = var.node_update_max_unavailable
  }

  # Ignore changes to desired_size to prevent Terraform from overwriting autoscaler/Karpenter decisions.
  lifecycle {
    ignore_changes = [scaling_config[0].desired_size]
  }

  tags = merge(var.tags, {
    Name = local.node_group_name
  })

  depends_on = [
    aws_iam_role_policy_attachment.node_worker_policy,
    aws_iam_role_policy_attachment.node_cni_policy,
    aws_iam_role_policy_attachment.node_ecr_read,
    aws_iam_role_policy_attachment.node_ssm,
  ]
}
