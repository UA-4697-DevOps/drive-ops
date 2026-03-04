locals {
  oidc_host = var.oidc_provider_url  # вже без https:// (приходить з eks outputs)
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
      "arn:aws:secretsmanager:${var.aws_region}:${var.account_id}:secret:${var.project_name}/*",
    ]
  }
}

resource "aws_iam_policy" "eso_secrets" {
  name        = "Training-${var.project_name}-${var.env}-eso-secrets-policy"
  description = "Allow ESO to read drive-ops secrets from AWS Secrets Manager"
  policy      = data.aws_iam_policy_document.eso_secrets.json
  tags        = var.tags
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

resource "aws_iam_role" "eso" {
  name                 = "Training-${var.project_name}-${var.env}-eso-role"
  assume_role_policy   = data.aws_iam_policy_document.eso_assume_role.json
  permissions_boundary = "arn:aws:iam::${var.account_id}:policy/DevOpsBound"
  tags                 = var.tags
}

resource "aws_iam_role_policy_attachment" "eso_secrets" {
  role       = aws_iam_role.eso.name
  policy_arn = aws_iam_policy.eso_secrets.arn
}
