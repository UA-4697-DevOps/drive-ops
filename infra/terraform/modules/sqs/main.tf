# Create SQS FIFO queue for event messaging
resource "aws_sqs_queue" "main_queue" {
  name                        = "${var.queue_name}-${var.env}.fifo"
  fifo_queue                  = true
  content_based_deduplication = true

  visibility_timeout_seconds = var.visibility_timeout
  message_retention_seconds  = var.message_retention
  receive_wait_time_seconds  = 20 # Long polling to reduce costs

  # Configure Dead Letter Queue
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = var.max_receive_count
  })

  # Merge local tags with global project variables
  tags = merge(var.tags, {
    Project     = var.project_name
    Environment = var.env
    CostCenter  = var.cost_center
    ManagedBy   = "Terraform"
    Component   = "sqs-queue"
  })
}

# Create Dead Letter Queue (DLQ)
resource "aws_sqs_queue" "dlq" {
  name                      = "${var.queue_name}-dlq-${var.env}.fifo"
  fifo_queue                = true
  message_retention_seconds = 1209600 # 14 days

  # Ensure consistent tagging across all infrastructure
  tags = merge(var.tags, {
    Project     = var.project_name
    Environment = var.env
    CostCenter  = var.cost_center
    ManagedBy   = "Terraform"
    Component   = "sqs-dlq"
    Purpose     = "DeadLetterQueue"
  })
}

# IAM Policy for message consumers
resource "aws_iam_policy" "consumer_policy" {
  name        = "${var.queue_name}-consumer-policy-${var.env}"
  description = "Allow consuming messages from ${var.queue_name} queue"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
          "sqs:ChangeMessageVisibility"
        ]
        Resource = aws_sqs_queue.main_queue.arn
      }
    ]
  })

  tags = merge(var.tags, {
    Project     = var.project_name
    Environment = var.env
    CostCenter  = var.cost_center
    ManagedBy   = "Terraform"
    Component   = "iam-policy"
    PolicyType  = "consumer"
  })
}

# IAM Policy for message publishers
resource "aws_iam_policy" "publisher_policy" {
  name        = "${var.queue_name}-publisher-policy-${var.env}"
  description = "Allow publishing messages to ${var.queue_name} queue"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sqs:SendMessage",
          "sqs:GetQueueUrl"
        ]
        Resource = aws_sqs_queue.main_queue.arn
      }
    ]
  })

  tags = merge(var.tags, {
    Project     = var.project_name
    Environment = var.env
    CostCenter  = var.cost_center
    ManagedBy   = "Terraform"
    Component   = "iam-policy"
    PolicyType  = "publisher"
  })
}
