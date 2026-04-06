# ==============================================================================
# EKS MODULE – CLUSTER & NODE GROUP
# ==============================================================================
# Creates:
#   1. Security group for the EKS cluster (control-plane ↔ node communication)
#   2. CloudWatch log group for control-plane logs
#   3. EKS cluster (managed control plane)
#   4. Node launch template for worker instances
#   5. Managed node group with autoscaling
# ==============================================================================

# ------------------------------------------------------------------------------
# 1. EKS CLUSTER AND NODE SECURITY GROUP
# ------------------------------------------------------------------------------

resource "aws_security_group" "eks_cluster" {
  name        = "${local.cluster_name}-cluster-sg"
  description = "Security group for EKS cluster control plane"
  vpc_id      = var.vpc_id

  tags = merge(var.tags, {
    Name = "${local.cluster_name}-cluster-sg"
  })
}

# --- Default Security Group Rules ---
locals {
  default_security_group_rules = {
    cluster_egress = {
      type              = "egress"
      from_port         = 0
      to_port           = 0
      protocol          = "-1"
      cidr_blocks       = ["0.0.0.0/0"]
      source_sg_id      = null
      security_group_id = aws_security_group.eks_cluster.id
      description       = "Allow all outbound traffic from control plane"
    }
    cluster_ingress_nodes = {
      type              = "ingress"
      from_port         = 443
      to_port           = 443
      protocol          = "tcp"
      cidr_blocks       = null
      source_sg_id      = aws_security_group.eks_nodes.id
      security_group_id = aws_security_group.eks_cluster.id
      description       = "Allow worker nodes to reach the API server"
    }
    nodes_egress = {
      type              = "egress"
      from_port         = 0
      to_port           = 0
      protocol          = "-1"
      cidr_blocks       = ["0.0.0.0/0"]
      source_sg_id      = null
      security_group_id = aws_security_group.eks_nodes.id
      description       = "Allow all outbound traffic from worker nodes"
    }
    nodes_internal = {
      type              = "ingress"
      from_port         = 0
      to_port           = 0
      protocol          = "-1"
      cidr_blocks       = null
      source_sg_id      = aws_security_group.eks_nodes.id
      security_group_id = aws_security_group.eks_nodes.id
      description       = "Allow node-to-node communication (all protocols including UDP and ICMP for CoreDNS and PMTU)"
    }
    nodes_ingress_cluster = {
      type              = "ingress"
      from_port         = 1025
      to_port           = 65535
      protocol          = "tcp"
      cidr_blocks       = null
      source_sg_id      = aws_security_group.eks_cluster.id
      security_group_id = aws_security_group.eks_nodes.id
      description       = "Allow control plane to reach worker nodes (kubelet, kube-proxy)"
    }
    nodes_ingress_cluster_443 = {
      type              = "ingress"
      from_port         = 443
      to_port           = 443
      protocol          = "tcp"
      cidr_blocks       = null
      source_sg_id      = aws_security_group.eks_cluster.id
      security_group_id = aws_security_group.eks_nodes.id
      description       = "Allow control plane to reach webhook endpoints on nodes"
    }
  }

  bastion_security_group_rules = var.bastion_security_group_id == null ? {} : {
    cluster_ingress_bastion_api = {
      type              = "ingress"
      from_port         = 443
      to_port           = 443
      protocol          = "tcp"
      cidr_blocks       = null
      source_sg_id      = var.bastion_security_group_id
      security_group_id = aws_security_group.eks_cluster.id
      description       = "Allow Bastion to communicate with EKS Control Plane API"
    }
  }

  # Merge default rules with user-provided custom rules
  all_security_group_rules = merge(
    local.default_security_group_rules,
    local.bastion_security_group_rules,
    var.custom_security_group_rules
  )

  # Principals granted cluster-admin in this module:
  # - dedicated EKS admin access role (always)
  # - optional bastion role (break-glass/admin automation)
  # - optional extra admin roles
  bastion_access_entries = merge(
    {
      eks_admin = module.eks_admin_access_role.iam_role_arn
    },
    var.bastion_role_arn == null ? {} : {
      bastion = var.bastion_role_arn
    }
  )
}

# --- Consolidated Security Group Rules ---
# Allow unrestricted egress from cluster to reach AWS services and external APIs.
# Nodes run in private subnets; outbound traffic exits via the NAT instance.
resource "aws_security_group_rule" "this" {
  for_each = local.all_security_group_rules

  type              = each.value.type
  from_port         = each.value.from_port
  to_port           = each.value.to_port
  protocol          = each.value.protocol
  cidr_blocks       = each.value.cidr_blocks
  security_group_id = each.value.security_group_id
  description       = each.value.description

  # Conditionally set source_security_group_id only if provided
  source_security_group_id = each.value.source_sg_id

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group" "eks_nodes" {
  name        = "${local.cluster_name}-node-sg"
  description = "Security group for EKS worker nodes"
  vpc_id      = var.vpc_id

  tags = merge(var.tags, {
    Name = "${local.cluster_name}-node-sg"
  })
}

resource "aws_security_group_rule" "db_ingress_from_eks_nodes_postgres" {
  count = var.db_security_group_id == null ? 0 : 1

  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.eks_nodes.id
  security_group_id        = var.db_security_group_id
  description              = "Allow EKS worker nodes to reach PostgreSQL"
}

# ------------------------------------------------------------------------------
# 2. CLOUDWATCH LOG GROUP (CONTROL PLANE LOGS)
# ------------------------------------------------------------------------------

resource "aws_cloudwatch_log_group" "eks" {
  name              = "/aws/eks/${local.cluster_name}/cluster"
  retention_in_days = var.cluster_log_retention_in_days
  kms_key_id        = var.kms_key_arn
  tags              = var.tags
}

# ------------------------------------------------------------------------------
# 3. EKS CLUSTER
# ------------------------------------------------------------------------------

resource "aws_eks_cluster" "this" {
  name     = local.cluster_name
  version  = var.cluster_version
  role_arn = module.eks_cluster_role.iam_role_arn

  # API endpoint access is controlled via cluster_endpoint_public_access and
  # cluster_endpoint_private_access variables. In dev, public access is disabled
  # and engineers reach the API via bastion or VPN.
  vpc_config {
    subnet_ids              = local.cluster_subnet_ids
    security_group_ids      = [aws_security_group.eks_cluster.id]
    endpoint_public_access  = var.cluster_endpoint_public_access
    endpoint_private_access = var.cluster_endpoint_private_access
    public_access_cidrs     = var.cluster_endpoint_public_access_cidrs
  }

  access_config {
    authentication_mode = "API_AND_CONFIG_MAP"
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

  # Ensure IAM role module and log group are created before the cluster
  depends_on = [
    module.eks_cluster_role,
    aws_cloudwatch_log_group.eks,
  ]
}

# ------------------------------------------------------------------------------
# 4. NODE LAUNCH TEMPLATE
# ------------------------------------------------------------------------------

resource "aws_launch_template" "eks_nodes" {
  for_each = var.node_groups

  name_prefix = "${local.cluster_name}-${each.key}-lt-"

  network_interfaces {
    associate_public_ip_address = each.value.associate_public_ip
    security_groups             = [aws_security_group.eks_nodes.id]
    delete_on_termination       = true
  }

  block_device_mappings {
    device_name = "/dev/xvda"
    ebs {
      volume_size           = each.value.disk_size
      volume_type           = "gp3"
      delete_on_termination = true
      encrypted             = true
    }
  }

  # IMDSv2 required; IRSA uses projected service account tokens, not instance IMDS.
  # Reducing hop_limit to 1 prevents pods from reaching instance IMDS (Checkov CKV_AWS_341).
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }

  tag_specifications {
    resource_type = "instance"
    tags          = merge(var.tags, { Name = "${local.cluster_name}-${each.key}" })
  }

  tags = var.tags

  lifecycle {
    create_before_destroy = true
  }
}

# ------------------------------------------------------------------------------
# 5. MANAGED NODE GROUP
# ------------------------------------------------------------------------------

resource "aws_eks_node_group" "this" {
  for_each = var.node_groups

  cluster_name    = aws_eks_cluster.this.name
  node_group_name = "${local.cluster_name}-${each.key}"
  node_role_arn   = module.node_group_role.iam_role_arn
  subnet_ids      = local.resolved_node_subnet_ids

  instance_types = each.value.instance_types
  ami_type       = each.value.ami_type
  capacity_type  = each.value.capacity_type

  launch_template {
    id      = aws_launch_template.eks_nodes[each.key].id
    version = aws_launch_template.eks_nodes[each.key].latest_version
  }

  scaling_config {
    desired_size = each.value.desired_size
    min_size     = each.value.min_size
    max_size     = each.value.max_size
  }

  update_config {
    max_unavailable = each.value.update_max_unavailable
  }

  lifecycle {
    ignore_changes = [scaling_config[0].desired_size]
  }

  tags = merge(var.tags, each.value.tags, {
    Name = "${local.cluster_name}-${each.key}"
  })

  depends_on = [
    module.node_group_role,
  ]
}

# ------------------------------------------------------------------------------
# 6. EKS ACCESS ENTRIES (BASTION + HUMAN ADMIN ROLES)
# ------------------------------------------------------------------------------

# Grant configured principals full cluster admin access.
resource "aws_eks_access_entry" "bastion" {
  for_each = local.bastion_access_entries

  cluster_name  = aws_eks_cluster.this.name
  principal_arn = each.value
  type          = "STANDARD"
}

resource "aws_eks_access_policy_association" "bastion_admin" {
  for_each = local.bastion_access_entries

  cluster_name  = aws_eks_cluster.this.name
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"
  principal_arn = each.value

  access_scope {
    type = "cluster"
  }

  depends_on = [aws_eks_access_entry.bastion]
}
