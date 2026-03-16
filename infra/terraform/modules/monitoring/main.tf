# --- 1. Centralized Log Groups ---
# Creates CloudWatch Log Groups for each service with a specified retention period
resource "aws_cloudwatch_log_group" "services" {
  for_each          = var.service_names
  name              = "/${var.project_name}/${var.env}/${each.key}"
  retention_in_days = var.log_retention_days

  tags = { Name = "${var.project_name}-${var.env}-${each.key}-logs" }
}


resource "aws_sns_topic" "alerts" {
  name = "${var.project_name}-${var.env}-alerts"

  tags = { Name = "${var.project_name}-${var.env}-alerts-topic" }
}

resource "aws_sns_topic_policy" "default" {
  arn    = aws_sns_topic.alerts.arn
  policy = data.aws_iam_policy_document.sns_topic_policy.json
}

# IAM policy document allowing CloudWatch to publish to the SNS topic
data "aws_iam_policy_document" "sns_topic_policy" {
  statement {
    actions = ["SNS:Publish"]
    effect  = "Allow"
    principals {
      type        = "Service"
      identifiers = ["cloudwatch.amazonaws.com"]
    }
    resources = [aws_sns_topic.alerts.arn]
  }
}

#  Alarms

# RDS High CPU, monitors database load; alerts when CPU stays above threshold for two periods
resource "aws_cloudwatch_metric_alarm" "rds_cpu_high" {
  alarm_name          = "${var.project_name}-${var.env}-rds-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = "300"
  statistic           = "Average"
  threshold           = var.cpu_alarm_threshold
  alarm_description   = "RDS CPU > ${var.cpu_alarm_threshold}%"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  ok_actions = [aws_sns_topic.alerts.arn]

  dimensions = { DBInstanceIdentifier = var.rds_instance_id }
}

#  SQS Processing Delay, monitors message age in the queue to detect processing bottlenecks
resource "aws_cloudwatch_metric_alarm" "sqs_old_messages" {
  alarm_name          = "${var.project_name}-${var.env}-sqs-delay"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "ApproximateAgeOfOldestMessage"
  namespace           = "AWS/SQS"
  period              = "60"
  statistic           = "Maximum"
  threshold           = var.sqs_delay_threshold
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = { QueueName = var.sqs_queue_name }
}

# EC2 High CPU, iterates through provided instances to create individual CPU alarms
resource "aws_cloudwatch_metric_alarm" "ec2_cpu_high" {
  for_each            = var.ec2_instances
  alarm_name          = "${var.project_name}-${var.env}-${each.key}-cpu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = "60"
  statistic           = "Average"
  threshold           = 85
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = { InstanceId = each.value }
}

# EC2 Status Check Failed, triggers if the EC2 instance fails any underlying AWS hardware or software checks
resource "aws_cloudwatch_metric_alarm" "ec2_status_check" {
  for_each            = var.ec2_instances
  alarm_name          = "${var.project_name}-${var.env}-${each.key}-status-check"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "StatusCheckFailed"
  namespace           = "AWS/EC2"
  period              = "60"
  statistic           = "Maximum"
  threshold           = 0
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = { InstanceId = each.value }
}

# 4. Discord Integration (Lambda) 

resource "aws_lambda_function" "discord_notifier" {
  filename      = "${path.module}/dummy.zip"
  function_name = "${var.project_name}-${var.env}-discord-notifier"
  role          = module.lambda_iam_role.iam_role_arn
  handler       = "discord.lambda_handler"
  runtime       = "python3.12"
  timeout       = 30
  memory_size   = 128

  environment {
    variables = {
      DISCORD_SECRET_ARN = var.discord_webhook_secret_arn
    }
  }

  lifecycle {
    ignore_changes = [filename, source_code_hash]
  }

  tags = { Name = "${var.project_name}-${var.env}-discord-notifier" }
}

# ==============================================================================
# Lambda IAM Role
# ==============================================================================

module "lambda_iam_role" {
  source = "../iam-role"

  role_name            = "Training-${var.project_name}-${var.env}-lambda-discord-role"
  permissions_boundary = "arn:aws:iam::${var.account_id}:policy/DevOpsBound"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })

  managed_policy_arns = [
    "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
  ]

  inline_policies = {
    secrets_read = jsonencode({
      Version = "2012-10-17"
      Statement = [{
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = [var.discord_webhook_secret_arn]
      }]
    })
  }
}

#-------------- Moved IAM Role and Policies to module/iam-role --------------

moved {
  from = aws_iam_role.lambda_exec
  to   = module.lambda_iam_role.aws_iam_role.this
}

moved {
  from = aws_iam_role_policy_attachment.lambda_logs
  to   = module.lambda_iam_role.aws_iam_role_policy_attachment.managed_attach["arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"]
}

moved {
  from = aws_iam_role_policy.lambda_secrets_read
  to   = module.lambda_iam_role.aws_iam_role_policy.inline["secrets_read"]
}

# Subscribes the Lambda function to the SNS alerts topic
resource "aws_sns_topic_subscription" "discord_lambda" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "lambda"
  endpoint  = aws_lambda_function.discord_notifier.arn
}

# Grants SNS service permission to invoke the Lambda notifier function
resource "aws_lambda_permission" "with_sns" {
  statement_id  = "AllowExecutionFromSNS"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.discord_notifier.function_name
  principal     = "sns.amazonaws.com"
  source_arn    = aws_sns_topic.alerts.arn
}
