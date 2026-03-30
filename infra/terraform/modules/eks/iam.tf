# ==============================================================================
# EKS MODULE – IAM ROLES
# ==============================================================================
# Creates IAM roles using the iam-role module:
#   1. EKS Cluster Role    – assumed by the EKS control plane (via module)
#   2. Node Group Role      – assumed by EC2 worker nodes (via module)
#   3. Cluster Autoscaler IRSA Role – for pod-level access (direct resource)
# All roles use the Training- prefix and DevOpsBound permissions boundary
# to comply with the account-level IAM constraints.
# ==============================================================================

# ------------------------------------------------------------------------------
# 1. EKS CLUSTER ROLE (via iam-role module)
# ------------------------------------------------------------------------------

data "aws_iam_policy_document" "eks_cluster_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["eks.amazonaws.com"]
    }
  }
}

module "eks_cluster_role" {
  source = "../iam-role"

  role_name            = "${local.cluster_name}-cluster-role"
  assume_role_policy   = data.aws_iam_policy_document.eks_cluster_assume_role.json
  permissions_boundary = local.permissions_boundary

  managed_policy_arns = [
    "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy",
    "arn:aws:iam::aws:policy/AmazonEKSVPCResourceController"
  ]

  tags = var.tags
}

# ------------------------------------------------------------------------------
# 2. NODE GROUP ROLE (via iam-role module)
# ------------------------------------------------------------------------------

data "aws_iam_policy_document" "node_group_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

module "node_group_role" {
  source = "../iam-role"

  role_name            = "${local.cluster_name}-node-role"
  assume_role_policy   = data.aws_iam_policy_document.node_group_assume_role.json
  permissions_boundary = local.permissions_boundary

  managed_policy_arns = [
    "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy",
    "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy",
    "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly",
    "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
  ]

  tags = var.tags
}

# --- State Migrations for Cluster and Node Roles ---

moved {
  from = aws_iam_role.eks_cluster
  to   = module.eks_cluster_role.aws_iam_role.this
}

moved {
  from = aws_iam_role_policy_attachment.eks_cluster_policy
  to   = module.eks_cluster_role.aws_iam_role_policy_attachment.managed_attach["arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"]
}

moved {
  from = aws_iam_role_policy_attachment.eks_vpc_resource_controller
  to   = module.eks_cluster_role.aws_iam_role_policy_attachment.managed_attach["arn:aws:iam::aws:policy/AmazonEKSVPCResourceController"]
}

moved {
  from = aws_iam_role.node_group
  to   = module.node_group_role.aws_iam_role.this
}

moved {
  from = aws_iam_role_policy_attachment.node_worker_policy
  to   = module.node_group_role.aws_iam_role_policy_attachment.managed_attach["arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy"]
}

moved {
  from = aws_iam_role_policy_attachment.node_cni_policy
  to   = module.node_group_role.aws_iam_role_policy_attachment.managed_attach["arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"]
}

moved {
  from = aws_iam_role_policy_attachment.node_ecr_read
  to   = module.node_group_role.aws_iam_role_policy_attachment.managed_attach["arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"]
}

moved {
  from = aws_iam_role_policy_attachment.node_ssm
  to   = module.node_group_role.aws_iam_role_policy_attachment.managed_attach["arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"]
}

# ------------------------------------------------------------------------------
# 3. CLUSTER AUTOSCALER IRSA ROLE
# ------------------------------------------------------------------------------
# Allows the cluster-autoscaler ServiceAccount in kube-system to assume this
# role via IRSA, granting it permissions to manage Auto Scaling Groups.

data "aws_iam_policy_document" "cluster_autoscaler_assume_role" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.eks.arn]
    }
    condition {
      test     = "StringEquals"
      variable = "${replace(aws_eks_cluster.this.identity[0].oidc[0].issuer, "https://", "")}:sub"
      values   = ["system:serviceaccount:kube-system:cluster-autoscaler"]
    }
    condition {
      test     = "StringEquals"
      variable = "${replace(aws_eks_cluster.this.identity[0].oidc[0].issuer, "https://", "")}:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

module "cluster_autoscaler_role" {
  source = "../iam-role"

  role_name            = "${local.cluster_name}-cluster-autoscaler-role"
  assume_role_policy   = data.aws_iam_policy_document.cluster_autoscaler_assume_role.json
  permissions_boundary = local.permissions_boundary

  custom_policies = {
    "${local.cluster_name}-cluster-autoscaler-policy" = jsonencode({
      Version = "2012-10-17"
      Statement = [
        {
          Sid    = "AutoScalingRead"
          Effect = "Allow"
          Action = [
            "autoscaling:DescribeAutoScalingGroups",
            "autoscaling:DescribeAutoScalingInstances",
            "autoscaling:DescribeLaunchConfigurations",
            "autoscaling:DescribeScalingActivities",
            "autoscaling:DescribeTags",
          ]
          Resource = "*"
        },
        {
          Sid    = "AutoScalingWrite"
          Effect = "Allow"
          Action = [
            "autoscaling:SetDesiredCapacity",
            "autoscaling:TerminateInstanceInAutoScalingGroup",
          ]
          Resource = "*"
          Condition = {
            StringEquals = {
              "autoscaling:ResourceTag/k8s.io/cluster-autoscaler/${local.cluster_name}" = "owned"
              "autoscaling:ResourceTag/k8s.io/cluster-autoscaler/enabled"               = "true"
            }
          }
        },
        {
          Sid    = "EC2Describe"
          Effect = "Allow"
          Action = [
            "ec2:DescribeLaunchTemplateVersions",
            "ec2:DescribeInstanceTypes",
          ]
          Resource = "*"
        },
        {
          Sid    = "EKSDescribe"
          Effect = "Allow"
          Action = [
            "eks:DescribeNodegroup",
          ]
          Resource = "arn:aws:eks:${data.aws_region.current.id}:${var.account_id}:nodegroup/${local.cluster_name}/*/*"
        }
      ]
    })
  }

  custom_policies_descriptions = {
    "${local.cluster_name}-cluster-autoscaler-policy" = "Permissions for Cluster Autoscaler to manage EKS node group Auto Scaling Groups"
  }

  tags = var.tags
}

# --- State Migrations for Cluster Autoscaler Role ---

moved {
  from = aws_iam_role.cluster_autoscaler
  to   = module.cluster_autoscaler_role.aws_iam_role.this
}

moved {
  from = aws_iam_policy.cluster_autoscaler
  to   = module.cluster_autoscaler_role.aws_iam_policy.custom["${local.cluster_name}-cluster-autoscaler-policy"]
}

moved {
  from = aws_iam_role_policy_attachment.cluster_autoscaler
  to   = module.cluster_autoscaler_role.aws_iam_role_policy_attachment.custom_attach["${local.cluster_name}-cluster-autoscaler-policy"]
}
