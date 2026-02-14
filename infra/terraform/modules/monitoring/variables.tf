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

variable "ecs_cluster_name" {
  description = "The name of the ECS Cluster to monitor"
  type        = string
}

variable "sqs_queue_name" {
  description = "The name of the SQS FIFO queue to monitor"
  type        = string
}

variable "discord_webhook_url" {
  description = "The sensitive Discord Webhook URL for alerts"
  type        = string
  sensitive   = true
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
