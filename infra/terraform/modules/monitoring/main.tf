# --- 1. Centralized Log Groups ---
# Cost Optimization: Keep retention low for MVP
resource "aws_cloudwatch_log_group" "services" {
  for_each          = var.service_names
  name              = "/${var.project_name}/${var.env}/${each.key}"
  retention_in_days = var.log_retention_days

  tags = { Name = "${var.project_name}-${var.env}-${each.key}-logs" }
}

# --- 2. Notification Channel (SNS) ---
resource "aws_sns_topic" "alerts" {
  name = "${var.project_name}-${var.env}-alerts"

  # SSE: Enable server-side encryption using the AWS-managed key to protect data at rest
  kms_master_key_id = "alias/aws/sns"

  tags = { Name = "${var.project_name}-${var.env}-alerts-topic" }
}

# SNS Topic Policy: Allow CloudWatch to publish alerts
resource "aws_sns_topic_policy" "default" {
  arn    = aws_sns_topic.alerts.arn
  policy = data.aws_iam_policy_document.sns_topic_policy.json
}

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

# --- 3. Alarms ---

# A. RDS High CPU (Database Health)
resource "aws_cloudwatch_metric_alarm" "rds_cpu_high" {
  alarm_name          = "${var.project_name}-${var.env}-rds-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = "300"
  statistic           = "Average"
  threshold           = var.cpu_alarm_threshold
  alarm_description   = "RDS CPU > ${var.cpu_alarm_threshold}% for 10 mins"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]

  dimensions = {
    DBInstanceIdentifier = var.rds_instance_id
  }

  tags = { Name = "${var.project_name}-${var.env}-rds-cpu-alarm" }
}

# B. SQS Processing Delay (Worker Health)
resource "aws_cloudwatch_metric_alarm" "sqs_old_messages" {
  alarm_name          = "${var.project_name}-${var.env}-sqs-delay"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "ApproximateAgeOfOldestMessage"
  namespace           = "AWS/SQS"
  period              = "60"
  statistic           = "Maximum"
  threshold           = var.sqs_delay_threshold
  alarm_description   = "Messages stuck in queue > ${var.sqs_delay_threshold}s"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]

  dimensions = {
    QueueName = var.sqs_queue_name
  }

  tags = { Name = "${var.project_name}-${var.env}-sqs-delay-alarm" }
}

# C. ECS Service CPU High (Application Health)
resource "aws_cloudwatch_metric_alarm" "ecs_cpu_high" {
  for_each            = var.service_names
  alarm_name          = "${var.project_name}-${var.env}-${each.key}-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ECS"
  period              = "60"
  statistic           = "Average"
  threshold           = 85
  alarm_description   = "ECS Service CPU > 85%"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]

  dimensions = {
    ClusterName = var.ecs_cluster_name
    ServiceName = each.key
  }

  tags = { Name = "${var.project_name}-${var.env}-${each.key}-cpu-alarm" }
}

# --- 4. Discord Integration (Lambda) ---

data "archive_file" "discord_lambda_zip" {
  type        = "zip"
  source_file = "${path.module}/discord.py"
  output_path = "${path.module}/discord.zip"
}

resource "aws_lambda_function" "discord_notifier" {
  filename      = data.archive_file.discord_lambda_zip.output_path
  function_name = "${var.project_name}-${var.env}-discord-notifier"
  role          = aws_iam_role.lambda_exec.arn
  handler       = "discord.lambda_handler"
  runtime       = "python3.12"

  # Explicitly set timeout to 30s to handle external API latency
  timeout = 30
  # Set memory to 128MB (Standard for light functions)
  memory_size = 128

  source_code_hash = data.archive_file.discord_lambda_zip.output_base64sha256

  environment {
    variables = {
      DISCORD_WEBHOOK_URL = var.discord_webhook_url
    }
  }

  tags = { Name = "${var.project_name}-${var.env}-discord-notifier" }
}

# IAM Role with naming convention and boundary consistent with VPC module
resource "aws_iam_role" "lambda_exec" {
  name                 = "Training-${var.project_name}-${var.env}-lambda-discord-role"
  permissions_boundary = "arn:aws:iam::${var.account_id}:policy/DevOpsBound"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })

  tags = { Name = "Training-${var.project_name}-${var.env}-lambda-discord-role" }
}

# Attach policy to allow Lambda to create log streams
resource "aws_iam_role_policy_attachment" "lambda_logs" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Subscribe the Lambda function to the SNS topic
resource "aws_sns_topic_subscription" "discord_lambda" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "lambda"
  endpoint  = aws_lambda_function.discord_notifier.arn
}

# Grant SNS permission to invoke the Lambda function
resource "aws_lambda_permission" "with_sns" {
  statement_id  = "AllowExecutionFromSNS"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.discord_notifier.function_name
  principal     = "sns.amazonaws.com"
  source_arn    = aws_sns_topic.alerts.arn
}
