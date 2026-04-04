# --- General Project Variables ---

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

# --- Monitoring Specific Variables ---

variable "service_names" {
  description = "A set of service names to create CloudWatch Log Groups for"
  type        = set(string)
}

variable "rds_instance_id" {
  description = "The identifier of the RDS instance to monitor"
  type        = string
}

# --- UPDATED: Replaced ECS Cluster with EC2 Instances Map ---
# variable "ec2_instances" {
#   description = "Map of service names to EC2 Instance IDs for monitoring (e.g., { trip-service = 'i-0123456789abcdef0' })"
#   type        = map(string)
# }

variable "sqs_queue_name" {
  description = "The name of the SQS FIFO queue to monitor"
  type        = string
}

variable "discord_webhook_secret_arn" {
  description = "The ARN of the Secrets Manager secret containing the Discord Webhook URL"
  type        = string
}

# --- Alarm Thresholds & Settings ---

variable "cpu_alarm_threshold" {
  description = "The CPU utilization percentage threshold for the RDS alarm"
  type        = number
  default     = 80
}

variable "sqs_delay_threshold" {
  description = "The maximum age (in seconds) of the oldest message in the SQS queue before triggering an alarm"
  type        = number
  default     = 300
}

variable "log_retention_days" {
  description = "The number of days to retain CloudWatch log events"
  type        = number
  default     = 3 # Minimal retention to stay within Free Tier limits
}
