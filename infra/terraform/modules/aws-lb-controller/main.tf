# ==============================================================================
# AWS LOAD BALANCER CONTROLLER – IAM MODULE
# ==============================================================================

locals {
  oidc_host = var.oidc_provider_url
}

# IAM policy for AWS Load Balancer Controller
resource "aws_iam_policy" "alb_controller" {
  name        = "Training-${var.project_name}-${var.env}-alb-controller-policy"
  description = "IAM policy for AWS Load Balancer Controller"
  policy      = file("${path.module}/iam-policy.json")
  tags        = var.tags
}

# Trust policy for IRSA (IAM Roles for Service Accounts)
data "aws_iam_policy_document" "alb_controller_assume_role" {
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
      values   = ["system:serviceaccount:${var.namespace}:aws-load-balancer-controller"]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_host}:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

# IAM role for AWS Load Balancer Controller
resource "aws_iam_role" "alb_controller" {
  name                 = "Training-${var.project_name}-${var.env}-alb-controller-role"
  assume_role_policy   = data.aws_iam_policy_document.alb_controller_assume_role.json
  permissions_boundary = "arn:aws:iam::${var.account_id}:policy/DevOpsBound"
  tags                 = var.tags
}

# Attach policy to role
resource "aws_iam_role_policy_attachment" "alb_controller" {
  role       = aws_iam_role.alb_controller.name
  policy_arn = aws_iam_policy.alb_controller.arn
}
