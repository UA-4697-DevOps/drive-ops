# ==============================================================================
# AWS LOAD BALANCER CONTROLLER – IAM MODULE
# ==============================================================================

locals {
  oidc_host = var.oidc_provider_url
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

module "iam_role" {
  source = "../iam-role"

  role_name            = "Training-${var.project_name}-${var.env}-alb-controller-role"
  assume_role_policy   = data.aws_iam_policy_document.alb_controller_assume_role.json
  permissions_boundary = "arn:aws:iam::${var.account_id}:policy/DevOpsBound"
  custom_policies = {
    "Training-${var.project_name}-${var.env}-alb-controller-policy" = file("${path.module}/iam-policy.json")
  }
  custom_policies_descriptions = {
    "Training-${var.project_name}-${var.env}-alb-controller-policy" = "IAM policy for AWS Load Balancer Controller"
  }
  managed_policy_arns = []

  tags = var.tags
}



moved {
  from = aws_iam_policy.alb_controller
  to   = module.iam_role.aws_iam_policy.custom["Training-drive-ops-dev-alb-controller-policy"]
}

moved {
  from = aws_iam_role.alb_controller
  to   = module.iam_role.aws_iam_role.this
}

moved {
  from = aws_iam_role_policy_attachment.alb_controller
  to   = module.iam_role.aws_iam_role_policy_attachment.custom_attach["Training-drive-ops-dev-alb-controller-policy"]
}
