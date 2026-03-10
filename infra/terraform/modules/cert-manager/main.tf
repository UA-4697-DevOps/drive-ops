# ==============================================================================
# CERT-MANAGER – IAM MODULE
# ==============================================================================
# Creates an IRSA role for cert-manager to solve DNS-01 challenges via Route53.
# cert-manager itself is deployed as a Helm chart via ArgoCD.
# ==============================================================================

locals {
  oidc_host = var.oidc_provider_url
}

# IAM policy for cert-manager to manage Route53 records (DNS-01 challenge)
data "aws_iam_policy_document" "cert_manager" {
  statement {
    sid    = "AllowRoute53Change"
    effect = "Allow"
    actions = [
      "route53:GetChange",
    ]
    resources = ["arn:aws:route53:::change/*"]
  }

  statement {
    sid    = "AllowRoute53RecordSets"
    effect = "Allow"
    actions = [
      "route53:ChangeResourceRecordSets",
      "route53:ListResourceRecordSets",
    ]
    resources = [
      "arn:aws:route53:::hostedzone/${var.zone_id}",
    ]
  }

  statement {
    sid    = "AllowRoute53ListZones"
    effect = "Allow"
    actions = [
      "route53:ListHostedZones",
      "route53:ListHostedZonesByName",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_policy" "cert_manager" {
  name        = "Training-${var.project_name}-${var.env}-cert-manager-policy"
  description = "Allow cert-manager to manage Route53 records for DNS-01 challenges"
  policy      = data.aws_iam_policy_document.cert_manager.json
  tags        = var.tags
}

# Trust policy for IRSA (IAM Roles for Service Accounts)
data "aws_iam_policy_document" "cert_manager_assume_role" {
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
      values   = ["system:serviceaccount:${var.namespace}:cert-manager"]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_host}:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

# IAM role for cert-manager
resource "aws_iam_role" "cert_manager" {
  name                 = "Training-${var.project_name}-${var.env}-cert-manager-role"
  assume_role_policy   = data.aws_iam_policy_document.cert_manager_assume_role.json
  permissions_boundary = "arn:aws:iam::${var.account_id}:policy/DevOpsBound"
  tags                 = var.tags
}

# Attach policy to role
resource "aws_iam_role_policy_attachment" "cert_manager" {
  role       = aws_iam_role.cert_manager.name
  policy_arn = aws_iam_policy.cert_manager.arn
}
