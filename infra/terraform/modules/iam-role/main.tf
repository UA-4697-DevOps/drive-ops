resource "aws_iam_role" "this" {
  name                 = var.role_name
  assume_role_policy   = var.assume_role_policy
  description          = var.role_description
  permissions_boundary = var.permissions_boundary
  tags                 = var.tags
}

locals {
  normalized_custom_policies = {
    for key, value in var.custom_policies : key => {
      policy_name = can(value.policy) ? try(tostring(value.policy_name), key) : key
      policy      = can(value.policy) ? tostring(value.policy) : tostring(value)
      description = can(value.policy) ? try(tostring(coalesce(value.description, lookup(var.custom_policies_descriptions, try(value.policy_name, key), null))), null) : try(tostring(lookup(var.custom_policies_descriptions, key, null)), null)
    }
  }
}

resource "aws_iam_policy" "custom" {
  for_each = local.normalized_custom_policies

  name        = each.value.policy_name
  description = coalesce(each.value.description, "Custom policy ${each.value.policy_name} for ${var.role_name}")
  policy      = each.value.policy
  tags        = var.tags
}

resource "aws_iam_role_policy_attachment" "custom_attach" {
  for_each   = aws_iam_policy.custom
  role       = aws_iam_role.this.name
  policy_arn = each.value.arn
}

resource "aws_iam_role_policy_attachment" "managed_attach" {
  for_each   = toset(var.managed_policy_arns)
  role       = aws_iam_role.this.name
  policy_arn = each.key
}

resource "aws_iam_role_policy" "inline" {
  for_each = var.inline_policies
  name     = each.key
  role     = aws_iam_role.this.id
  policy   = each.value
}

resource "aws_iam_instance_profile" "this" {
  count = var.create_instance_profile ? 1 : 0
  name  = var.role_name
  role  = aws_iam_role.this.name
  tags  = var.tags
}