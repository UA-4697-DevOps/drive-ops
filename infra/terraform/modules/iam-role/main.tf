resource "aws_iam_role" "this" {
  name               = var.role_name
  assume_role_policy = var.assume_role_policy
  description        = var.role_description
  tags               = var.tags
}

resource "aws_iam_policy" "custom" {
  for_each    = var.custom_policies
  name        = each.key
  description = "Custom policy ${each.key} for ${var.role_name}"
  policy      = each.value
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
