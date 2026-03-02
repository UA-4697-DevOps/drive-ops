data "aws_region" "current" {}

locals {
  policies = {
    "tag-auditor" = {
      Statement = [
        {
          Action   = ["tag:GetResources", "tag:GetTagKeys", "tag:GetTagValues", "ec2:DescribeInstances", "rds:DescribeDBInstances", "sqs:ListQueues", "sqs:GetQueueAttributes", "secretsmanager:ListSecrets", "sts:GetCallerIdentity"]
          Effect   = "Allow"
          Resource = "*"
        },
        {
          Action   = ["sns:Publish"]
          Effect   = "Allow"
          Resource = var.sns_topic_arn
        },
        {
          Action   = ["lambda:InvokeFunction"]
          Effect   = "Allow"
          Resource = "arn:aws:lambda:${data.aws_region.current.id}:${var.account_id}:function:${var.project_name}-${var.env}-tag-cleanup"
        }
      ]
    },
    "tag-cleanup" = {
      Statement = [
        {
          Action   = ["ec2:TerminateInstances"]
          Effect   = "Allow"
          Resource = "arn:aws:ec2:*:${var.account_id}:instance/*"
        },
        {
          Action   = ["sns:Publish"]
          Effect   = "Allow"
          Resource = var.sns_topic_arn
        }
      ]
    }
  }
}

data "archive_file" "dummy" {
  type        = "zip"
  output_path = "${path.module}/dummy_generated.zip"

  source {
    content  = "# Dummy payload"
    filename = "dummy.txt"
  }
}

resource "aws_iam_role" "this" {
  for_each = var.lambda_functions

  name                 = "Training-${var.project_name}-${var.env}-${each.key}-role"
  permissions_boundary = "arn:aws:iam::${var.account_id}:policy/DevOpsBound"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "basic_exec" {
  for_each = var.lambda_functions

  role       = aws_iam_role.this[each.key].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "custom_policy" {
  for_each = { for k, v in var.lambda_functions : k => v if contains(keys(local.policies), k) }

  name = "Training-${var.project_name}-${var.env}-${each.key}-policy"
  role = aws_iam_role.this[each.key].id

  policy = jsonencode({
    Version   = "2012-10-17"
    Statement = local.policies[each.key].Statement
  })
}

resource "aws_lambda_function" "this" {
  for_each = var.lambda_functions

  function_name = "${var.project_name}-${var.env}-${each.key}"
  filename      = data.archive_file.dummy.output_path

  role        = aws_iam_role.this[each.key].arn
  handler     = each.value.handler
  runtime     = each.value.runtime
  timeout     = each.value.timeout
  memory_size = each.value.memory_size
  description = each.value.description

  environment {
    variables = merge(
      { SNS_TOPIC_ARN = var.sns_topic_arn },
      each.key == "tag-auditor" ? {
        CLEANUP_FUNCTION_NAME = "${var.project_name}-${var.env}-tag-cleanup"
        MANDATORY_TAGS        = var.mandatory_tags
      } : {}
    )
  }

  lifecycle {
    ignore_changes = [filename, source_code_hash]
  }

  tags = { Name = "${var.project_name}-${var.env}-${each.key}" }
}

resource "aws_cloudwatch_log_group" "logs" {
  for_each = var.lambda_functions

  name              = "/aws/lambda/${aws_lambda_function.this[each.key].function_name}"
  retention_in_days = 3
  tags              = { Name = "${var.project_name}-${var.env}-${each.key}-logs" }
}

resource "aws_cloudwatch_event_rule" "schedule" {
  for_each = { for k, v in var.lambda_functions : k => v if v.schedule != null }

  name                = "${var.project_name}-${var.env}-${each.key}-schedule"
  description         = "Trigger for ${each.key}"
  schedule_expression = each.value.schedule
}

resource "aws_cloudwatch_event_target" "lambda_target" {
  for_each = { for k, v in var.lambda_functions : k => v if v.schedule != null }

  rule      = aws_cloudwatch_event_rule.schedule[each.key].name
  target_id = "${each.key}-target"
  arn       = aws_lambda_function.this[each.key].arn
}

resource "aws_lambda_permission" "allow_eventbridge" {
  for_each = { for k, v in var.lambda_functions : k => v if v.schedule != null }

  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.this[each.key].function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.schedule[each.key].arn
}
