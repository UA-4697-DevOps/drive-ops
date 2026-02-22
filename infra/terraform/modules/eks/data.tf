# ==============================================================================
# EKS MODULE – DATA SOURCES & LOCALS
# ==============================================================================

data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

locals {
  cluster_name    = "Training-${var.project_name}-${var.env}-eks"
  node_group_name = "${local.cluster_name}-nodes"

  # Permissions boundary required by the DevOpsBound policy in this account
  permissions_boundary = var.account_id != null ? "arn:aws:iam::${var.account_id}:policy/DevOpsBound" : null

  # All subnets (public + private) for EKS cluster networking
  cluster_subnet_ids = concat(var.public_subnet_ids, var.private_subnet_ids)

  # Node subnets: explicit override or fall back to private subnets.
  # In NATless VPCs, pass public_subnet_ids via node_subnet_ids so nodes
  # can reach the EKS control plane and AWS APIs without a NAT gateway.
  resolved_node_subnet_ids = length(var.node_subnet_ids) > 0 ? var.node_subnet_ids : var.private_subnet_ids
}
