variable "service_names" {
  description = "A set of service names to create CloudWatch Log Groups for"
  type        = set(string)
  # Examples: ["trip-service", "driver-service", "client-gateway"] from ai.md
}

variable "sns_topic_arn" {
  description = "the ARN of the SNS topic to send alarm notifications to"
  type        = string
}

variable "rds_instance_id" {
  description = "The identifier of the RDS instance to monitor"
  type        = string
}
