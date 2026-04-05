output "karpenter_role_arn" {
  description = "ARN of the Karpenter controller IRSA role"
  value       = module.karpenter_irsa.iam_role_arn
}

output "karpenter_role_name" {
  description = "Name of the Karpenter controller IRSA role"
  value       = module.karpenter_irsa.iam_role_name
}

output "interruption_queue_url" {
  description = "URL of the SQS interruption queue"
  value       = aws_sqs_queue.interruption.url
}

output "interruption_queue_arn" {
  description = "ARN of the SQS interruption queue"
  value       = aws_sqs_queue.interruption.arn
}
