# ==============================================================================
# EXTERNAL DNS – IAM MODULE
# ==============================================================================

locals {
  oidc_host = var.oidc_provider_url
}

# IAM policy for External DNS to manage Route53 records
data "aws_iam_policy_document" "external_dns" {
  statement {
    sid    = "ManageRoute53Records"
    effect = "Allow"
    actions = [
      "route53:ChangeResourceRecordSets",
    ]
    resources = [
      "arn:aws:route53:::hostedzone/${var.zone_id}",
    ]
  }

  statement {
    sid    = "ListRoute53HostedZones"
    effect = "Allow"
    actions = [
      "route53:ListHostedZones",
      "route53:ListResourceRecordSets",
      "route53:ListTagsForResource",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_policy" "external_dns" {
  name        = "Training-${var.project_name}-${var.env}-external-dns-policy"
  description = "Allow External DNS to manage Route53 records"
  policy      = data.aws_iam_policy_document.external_dns.json
  tags        = var.tags
}

# Trust policy for IRSA (IAM Roles for Service Accounts)
data "aws_iam_policy_document" "external_dns_assume_role" {
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
      values   = ["system:serviceaccount:${var.namespace}:external-dns"]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_host}:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

# IAM role for External DNS
resource "aws_iam_role" "external_dns" {
  name                 = "Training-${var.project_name}-${var.env}-external-dns-role"
  assume_role_policy   = data.aws_iam_policy_document.external_dns_assume_role.json
  permissions_boundary = "arn:aws:iam::${var.account_id}:policy/DevOpsBound"
  tags                 = var.tags
}

# Attach policy to role
resource "aws_iam_role_policy_attachment" "external_dns" {
  role       = aws_iam_role.external_dns.name
  policy_arn = aws_iam_policy.external_dns.arn
}
