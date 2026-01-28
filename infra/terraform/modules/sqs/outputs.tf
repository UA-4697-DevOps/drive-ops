output "queue_url" {
  description = "The URL of the SQS queue"
  value       = aws_sqs_queue.main_queue.url
}

output "queue_arn" {
  description = "The ARN of the SQS queue"
  value       = aws_sqs_queue.main_queue.arn
}

output "queue_name" {
  description = "The name of the SQS queue"
  value       = aws_sqs_queue.main_queue.name
}

output "dlq_url" {
  description = "The URL of the Dead Letter Queue"
  value       = aws_sqs_queue.dlq.url
}

output "dlq_arn" {
  description = "The ARN of the Dead Letter Queue"
  value       = aws_sqs_queue.dlq.arn
}

output "dlq_name" {
  description = "The name of the Dead Letter Queue"
  value       = aws_sqs_queue.dlq.name
}

output "consumer_policy_arn" {
  description = "The ARN of the IAM policy for consumers"
  value       = aws_iam_policy.consumer_policy.arn
}

output "publisher_policy_arn" {
  description = "The ARN of the IAM policy for publishers"
  value       = aws_iam_policy.publisher_policy.arn
}
