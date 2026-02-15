# --- 1. Centralized Log Groups ---
resource "aws_cloudwatch_log_group" "services" {
  for_each          = var.service_names
  name              = "/${var.project_name}/${var.env}/${each.key}"
  retention_in_days = var.log_retention_days

  tags = { Name = "${var.project_name}-${var.env}-${each.key}-logs" }
}

# --- 2. Notification Channel (SNS) ---
resource "aws_sns_topic" "alerts" {
  name = "${var.project_name}-${var.env}-alerts"
  # kms_master_key_id = "alias/aws/sns"

  tags = { Name = "${var.project_name}-${var.env}-alerts-topic" }
}

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

# --- 3. Data Source for Discord Webhook ---
# Fetches the secret value at deployment time to inject into Lambda
data "aws_secretsmanager_secret_version" "discord_url" {
  secret_id = var.discord_webhook_secret_arn
}

# --- 4. Alarms ---

# A. RDS High CPU
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
  ok_actions          = [aws_sns_topic.alerts.arn]

  dimensions = { DBInstanceIdentifier = var.rds_instance_id }
}

# B. SQS Processing Delay
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
  ok_actions          = [aws_sns_topic.alerts.arn]

  dimensions = { QueueName = var.sqs_queue_name }
}

# C. EC2 High CPU
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
  ok_actions          = [aws_sns_topic.alerts.arn]

  dimensions = { InstanceId = each.value }
}

# D. EC2 Status Check Failed
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
  ok_actions          = [aws_sns_topic.alerts.arn]

  dimensions = { InstanceId = each.value }
}

# --- 5. Discord Integration (Lambda) ---

data "archive_file" "discord_lambda_zip" {
  type        = "zip"
  source_file = "${path.module}/discord.py"
  output_path = "${path.module}/discord.zip"
}

resource "aws_lambda_function" "discord_notifier" {
  filename         = data.archive_file.discord_lambda_zip.output_path
  function_name    = "${var.project_name}-${var.env}-discord-notifier"
  role             = aws_iam_role.lambda_exec.arn
  handler          = "discord.lambda_handler"
  runtime          = "python3.12"
  timeout          = 30
  memory_size      = 128
  source_code_hash = data.archive_file.discord_lambda_zip.output_base64sha256

  environment {
    variables = {
      # Extracts the 'url' key from the JSON stored in Secrets Manager
      DISCORD_WEBHOOK_URL = jsondecode(data.aws_secretsmanager_secret_version.discord_url.secret_string)["url"]
    }
  }

  tags = { Name = "${var.project_name}-${var.env}-discord-notifier" }
}

# IAM Role for Lambda
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
}

resource "aws_iam_role_policy_attachment" "lambda_logs" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# NEW: Explicit permission to read the Discord Secret
resource "aws_iam_role_policy" "lambda_secrets_read" {
  name = "Training-${var.project_name}-${var.env}-lambda-secrets-policy"
  role = aws_iam_role.lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = [var.discord_webhook_secret_arn]
    }]
  })
}

resource "aws_sns_topic_subscription" "discord_lambda" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "lambda"
  endpoint  = aws_lambda_function.discord_notifier.arn
}

resource "aws_lambda_permission" "with_sns" {
  statement_id  = "AllowExecutionFromSNS"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.discord_notifier.function_name
  principal     = "sns.amazonaws.com"
  source_arn    = aws_sns_topic.alerts.arn
}
