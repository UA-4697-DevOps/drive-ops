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
    ]
    resources = ["*"]
  }

  statement {
    sid    = "ReadRoute53HostedZoneRecords"
    effect = "Allow"
    actions = [
      "route53:ListResourceRecordSets",
      "route53:ListTagsForResource",
    ]
    resources = [
      "arn:aws:route53:::hostedzone/${var.zone_id}",
    ]
  }
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

module "external_dns_iam_role" {
  source = "../iam-role"

  role_name            = "Training-${var.project_name}-${var.env}-external-dns-role"
  permissions_boundary = "arn:aws:iam::${var.account_id}:policy/DevOpsBound"
  assume_role_policy   = data.aws_iam_policy_document.external_dns_assume_role.json
  tags                 = var.tags

  custom_policies = {
    "Training-${var.project_name}-${var.env}-external-dns-policy" = data.aws_iam_policy_document.external_dns.json
  }

  custom_policies_descriptions = {
    "Training-${var.project_name}-${var.env}-external-dns-policy" = "Allow External DNS to manage Route53 records"
  }
}

# --- State Migrations for External DNS IAM Role ---

moved {
  from = aws_iam_role.external_dns
  to   = module.external_dns_iam_role.aws_iam_role.this
}

moved {
  from = aws_iam_policy.external_dns
  to   = module.external_dns_iam_role.aws_iam_policy.custom["Training-${var.project_name}-${var.env}-external-dns-policy"]
}

moved {
  from = aws_iam_role_policy_attachment.external_dns
  to   = module.external_dns_iam_role.aws_iam_role_policy_attachment.custom_attach["Training-${var.project_name}-${var.env}-external-dns-policy"]
}


