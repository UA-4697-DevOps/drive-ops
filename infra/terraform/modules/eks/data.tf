# ==============================================================================
# EKS MODULE – DATA SOURCES & LOCALS
# ==============================================================================

data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

locals {
  cluster_name = var.cluster_name_prefix != null && var.cluster_name_prefix != "" ? "${var.cluster_name_prefix}${var.project_name}-${var.env}-eks" : "${var.project_name}-${var.env}-eks"

  # Safe cluster name for IAM roles: AWS limit is 64 chars (role_name + "-cluster-role" or "-node-role")
  # Strategy: truncate to 40 chars, append "-" + first 5 chars of md5(cluster_name) for uniqueness
  # Result: 46 chars max, leaving room for suffixes like "-cluster-role" (13) or "-node-role" (10)
  safe_cluster_name = "${substr(local.cluster_name, 0, 40)}-${substr(md5(local.cluster_name), 0, 5)}"

  # Permissions boundary required by the DevOpsBound policy in this account
  permissions_boundary = "arn:aws:iam::${var.account_id}:policy/DevOpsBound"

  # All subnets (public + private) for EKS cluster networking
  cluster_subnet_ids = concat(var.public_subnet_ids, var.private_subnet_ids)

  # Node subnets: explicit override or fall back to private subnets.
  # Ensure null-safety with coalesce for var.node_subnet_ids.
  resolved_node_subnet_ids = length(coalesce(var.node_subnet_ids, [])) > 0 ? var.node_subnet_ids : var.private_subnet_ids

  # Safe node group name: EKS limit is 63 chars (node_group_name must include "-nodes")
  # Strategy: truncate cluster_name to 56 chars, append "-nodes" (7 chars)
  node_group_name = "${substr(local.cluster_name, 0, 56)}-nodes"
}
