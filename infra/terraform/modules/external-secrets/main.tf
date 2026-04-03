# ==============================================================================
# EXTERNAL SECRETS OPERATOR – IAM MODULE
# ==============================================================================

locals {
  oidc_host = var.oidc_provider_url
}

data "aws_iam_policy_document" "eso_secrets" {
  statement {
    sid    = "ReadDriveOpsSecrets"
    effect = "Allow"
    actions = [
      "secretsmanager:GetSecretValue",
      "secretsmanager:DescribeSecret",
    ]
    resources = [
      "arn:aws:secretsmanager:${var.aws_region}:${var.account_id}:secret:${var.project_name}/${var.env}/*",
    ]
  }
}


data "aws_iam_policy_document" "eso_assume_role" {
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
      values   = ["system:serviceaccount:${var.eso_namespace}:external-secrets"]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_host}:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}


module "eso_iam_role" {
  source = "../iam-role"

  role_name            = "Training-${var.project_name}-${var.env}-eso-role"
  permissions_boundary = "arn:aws:iam::${var.account_id}:policy/DevOpsBound"
  assume_role_policy   = data.aws_iam_policy_document.eso_assume_role.json
  tags                 = var.tags

  custom_policies = {
    "Training-${var.project_name}-${var.env}-eso-secrets-policy" = data.aws_iam_policy_document.eso_secrets.json
  }

  custom_policies_descriptions = {
    "Training-${var.project_name}-${var.env}-eso-secrets-policy" = "Allow ESO to read drive-ops secrets from AWS Secrets Manager"
  }
}

# --- State Migrations for ESO IAM Role ---

moved {
  from = aws_iam_role.eso
  to   = module.eso_iam_role.aws_iam_role.this
}
