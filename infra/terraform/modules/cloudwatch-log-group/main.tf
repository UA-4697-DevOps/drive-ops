resource "aws_cloudwatch_log_group" "this" {
  for_each = var.log_groups

  name              = each.value.name
  retention_in_days = coalesce(each.value.retention_in_days, var.retention_days)
  kms_key_id        = each.value.kms_key_id

  tags = merge(var.tags, {
    Name = each.value.name
  })
}
