# ==============================================================================
# CLUSTER AUTOSCALER – IAM MODULE
# ==============================================================================
locals {
  oidc_host    = var.oidc_provider_url
  cluster_name = var.cluster_name
}

data "aws_region" "current" {}

data "aws_iam_policy_document" "cluster_autoscaler" {
  statement {
    sid    = "ReadOnly"
    effect = "Allow"
    actions = [
      "autoscaling:DescribeAutoScalingGroups",
      "autoscaling:DescribeAutoScalingInstances",
      "autoscaling:DescribeLaunchConfigurations",
      "autoscaling:DescribeScalingActivities",
      "autoscaling:DescribeTags",
      "ec2:DescribeImages",
      "ec2:DescribeInstanceTypes",
      "ec2:DescribeLaunchTemplateVersions",
      "ec2:GetInstanceTypesFromInstanceRequirements",
    ]
    resources = ["*"]
  }

  statement {
    sid    = "DescribeNodegroup"
    effect = "Allow"
    actions = [
      "eks:DescribeNodegroup",
    ]
    resources = [
      "arn:aws:eks:${data.aws_region.current.name}:${var.account_id}:nodegroup/${local.cluster_name}/*/*",
    ]
  }

  statement {
    sid    = "WriteScaling"
    effect = "Allow"
    actions = [
      "autoscaling:SetDesiredCapacity",
      "autoscaling:TerminateInstanceInAutoScalingGroup",
    ]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "autoscaling:ResourceTag/k8s.io/cluster-autoscaler/${local.cluster_name}"
      values   = ["owned"]
    }
    condition {
      test     = "StringEquals"
      variable = "autoscaling:ResourceTag/k8s.io/cluster-autoscaler/enabled"
      values   = ["true"]
    }
  }
}

# IAM policy for Cluster Autoscaler
resource "aws_iam_policy" "cluster_autoscaler" {
  name        = "Training-${var.project_name}-${var.env}-cluster-autoscaler-policy"
  description = "IAM policy for Kubernetes Cluster Autoscaler"
  policy      = data.aws_iam_policy_document.cluster_autoscaler.json
  tags        = var.tags
}

# Trust policy for IRSA (IAM Roles for Service Accounts)
data "aws_iam_policy_document" "cluster_autoscaler_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [var.oidc_provider_arn]
    }
    condition {
      test     = "StringEquals"
      variable = "${local.oidc_host}:sub"
      values   = ["system:serviceaccount:${var.namespace}:cluster-autoscaler"]
    }
    condition {
      test     = "StringEquals"
      variable = "${local.oidc_host}:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

# IAM role for Cluster Autoscaler
resource "aws_iam_role" "cluster_autoscaler" {
  name                 = "Training-${var.project_name}-${var.env}-cluster-autoscaler-role"
  assume_role_policy   = data.aws_iam_policy_document.cluster_autoscaler_assume_role.json
  permissions_boundary = "arn:aws:iam::${var.account_id}:policy/DevOpsBound"
  tags                 = var.tags
}

# Attach policy to role
resource "aws_iam_role_policy_attachment" "cluster_autoscaler" {
  role       = aws_iam_role.cluster_autoscaler.name
  policy_arn = aws_iam_policy.cluster_autoscaler.arn
}
