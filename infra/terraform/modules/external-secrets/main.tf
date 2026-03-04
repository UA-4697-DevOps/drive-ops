# ==============================================================================
# EXTERNAL SECRETS OPERATOR – IRSA
# ==============================================================================
# Creates:
#   1. IAM Role for External Secrets Operator Service Account (IRSA)
#   2. IAM Policy granting access to AWS Secrets Manager
#   3. Role-Policy attachment
#
# The ESO operator uses this role to sync secrets from AWS Secrets Manager
# into Kubernetes Secret objects via the ExternalSecret CRD.
# ==============================================================================

locals {
  eso_role_name = "${var.project_name}-${var.env}-external-secrets-role"
}

# ------------------------------------------------------------------------------
# 1. IAM POLICY – Secrets Manager Read Access
# ------------------------------------------------------------------------------
data "aws_iam_policy_document" "eso_secrets_policy" {
  statement {
    sid    = "AllowSecretsManagerRead"
    effect = "Allow"
    actions = [
      "secretsmanager:GetSecretValue",
      "secretsmanager:DescribeSecret"
    ]
    resources = [
      "arn:aws:secretsmanager:${var.aws_region}:${var.account_id}:secret:${var.project_name}/${var.env}/*"
    ]
  }
}

resource "aws_iam_policy" "eso_secrets_policy" {
  name        = "${local.eso_role_name}-policy"
  description = "Allow External Secrets Operator to read secrets from AWS Secrets Manager"
  policy      = data.aws_iam_policy_document.eso_secrets_policy.json
  tags        = var.tags
}

# ------------------------------------------------------------------------------
# 2. IAM ROLE – IRSA for ESO
# ------------------------------------------------------------------------------
data "aws_iam_policy_document" "eso_assume_role" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [var.oidc_provider_arn]
    }
    condition {
      test     = "StringEquals"
      variable = "${var.oidc_provider_url}:sub"
      values   = ["system:serviceaccount:external-secrets:external-secrets-sa"]
    }
    condition {
      test     = "StringEquals"
      variable = "${var.oidc_provider_url}:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "eso" {
  name                 = local.eso_role_name
  assume_role_policy   = data.aws_iam_policy_document.eso_assume_role.json
  permissions_boundary = "arn:aws:iam::${var.account_id}:policy/DevOpsBound"
  tags                 = var.tags
}

# ------------------------------------------------------------------------------
# 3. ROLE-POLICY ATTACHMENT
# ------------------------------------------------------------------------------
resource "aws_iam_role_policy_attachment" "eso" {
  role       = aws_iam_role.eso.name
  policy_arn = aws_iam_policy.eso_secrets_policy.arn
}
