variable "project_name" {
  type        = string
  description = "The name of the project, used for naming resources (e.g., drive-ops)"
}

variable "env" {
  type        = string
  description = "The deployment environment (e.g., dev, staging, prod)"
}

variable "account_id" {
  type        = string
  description = "The AWS Account ID"
}

variable "sns_topic_arn" {
  type        = string
  description = "ARN of the existing SNS alerts topic from the monitoring module"
}

variable "sqs_queue_arns" {
  type        = list(string)
  description = "List of SQS queue ARNs to scope GetQueueAttributes permission"
  default     = []
}
