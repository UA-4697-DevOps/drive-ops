# --- General Identification ---

variable "name" {
  description = "Name prefix for EC2 resources"
  type        = string
}

variable "project_name" {
  description = "The name of the project, used to construct SSM Parameter Store paths for config retrieval (e.g., drive-ops)"
  type        = string
  default     = null
}

variable "env" {
  description = "The deployment environment, used to construct SSM Parameter Store paths for config retrieval (e.g., dev)"
  type        = string
  default     = null
}

variable "service_name" {
  description = "Short service identifier for SSM Parameter Store path (e.g., trip-service, driver-service, client-gateway)"
  type        = string
  default     = null
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}

# --- Network & Compute ---

variable "vpc_id" {
  description = "VPC ID where EC2 instances will be deployed"
  type        = string
}

variable "subnet_id" {
  description = "Subnet ID for EC2 instance"
  type        = string
}

variable "ami" {
  description = "AMI ID for the EC2 instance"
  type        = string
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t3.micro"
}

variable "key_name" {
  description = "SSH key pair name"
  type        = string
  default     = null
}

variable "associate_public_ip_address" {
  description = "Associate a public IP address with the instance"
  type        = bool
  default     = true
}

variable "default_user" {
  description = "Default OS user on the AMI (e.g. admin for Debian, ubuntu for Ubuntu, ec2-user for AL2023)"
  type        = string
  default     = "admin"
}

# --- Storage ---

variable "root_volume_size" {
  description = "Size of the root volume in GB"
  type        = number
  default     = 20
}

variable "root_volume_type" {
  description = "Type of root volume (gp3, gp2, io1, io2)"
  type        = string
  default     = "gp3"
}

# --- Security & Access ---

variable "account_id" {
  description = "AWS account ID (used to construct IAM permissions boundary ARN)"
  type        = string
  default     = null
}

variable "iam_sqs_arns" {
  description = "List of SQS Queue ARNs that this EC2 instance is allowed to access (Send/Receive/Delete)"
  type        = list(string)
  default     = []
}

variable "iam_secret_arns" {
  description = "List of Secrets Manager Secret ARNs that this EC2 instance is allowed to read (GetSecretValue)"
  type        = list(string)
  default     = []
}

variable "ecr_repository_url" {
  description = "ECR repository URL for the service (enables ECR pull permission and creates the SSM deploy document)"
  type        = string
  default     = null
}

variable "additional_security_group_ids" {
  description = "Additional security group IDs to attach to the instance (e.g., sg-app for RDS access)"
  type        = list(string)
  default     = []
}

variable "enable_termination_protection" {
  description = "Enable EC2 instance termination protection"
  type        = bool
  default     = false
}

# --- Network Access Rules (Security Group) ---

variable "allowed_ssh_cidr_blocks" {
  description = "CIDR blocks allowed to SSH to the instance"
  type        = list(string)
  default     = []
}

variable "allowed_http_cidr_blocks" {
  description = "CIDR blocks allowed to access HTTP on the instance"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "allowed_https_cidr_blocks" {
  description = "CIDR blocks allowed to access HTTPS on the instance"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "app_port" {
  description = "Application port to allow inbound traffic on (0 = disabled)"
  type        = number
  default     = 0
}

variable "allowed_app_port_cidr_blocks" {
  description = "CIDR blocks allowed to access the application port"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

# --- Observability ---

variable "enable_monitoring" {
  description = "Enable detailed CloudWatch monitoring"
  type        = bool
  default     = false
}

# --- Customization ---

variable "user_data" {
  description = "User data script to run on instance launch (overrides default bootstrap if provided)"
  type        = string
  default     = null
}
