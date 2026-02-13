# 1. Create Log Groups for each service
resource "aws_cloudwatch_log_group" "services" {
  for_each          = var.service_names
  name              = "/drive-ops/dev/${each.key}"
  retention_in_days = 3 # Minimal retention to stay within Free Tier limits
}

# 2. CPU Utilization Alarm for RDS (PostgreSQL Primary)
resource "aws_cloudwatch_metric_alarm" "rds_cpu_high" {
  alarm_name          = "drive-ops-rds-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "This metric monitors RDS CPU utilization for the primary DB"
  alarm_actions       = [var.sns_topic_arn]

  dimensions = {
    DBInstanceIdentifier = var.rds_instance_id
  }
}

# 3. Processing Delay Alarm for SQS FIFO
resource "aws_cloudwatch_metric_alarm" "sqs_old_messages" {
  alarm_name          = "drive-ops-sqs-delay"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "ApproximateAgeOfOldestMessage"
  namespace           = "AWS/SQS"
  period              = "60"
  statistic           = "Maximum"
  threshold           = "300" # 5 minutes threshold
  alarm_description   = "Triggered if messages stay in the FIFO queue for too long"
  alarm_actions       = [var.sns_topic_arn]

  dimensions = {
    QueueName = "trip-created-dev.fifo" # Canonical name from project docs
  }
}