variable "name" {
  description = "Name prefix for EC2 resources"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID where EC2 instances will be deployed"
  type        = string
}

variable "subnet_id" {
  description = "Subnet ID for EC2 instance"
  type        = string
}

variable "ami" {
  description = "AMI ID for the EC2 instance (null = auto-select latest Amazon Linux 2023)"
  type        = string
  default     = null
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

variable "enable_monitoring" {
  description = "Enable detailed monitoring"
  type        = bool
  default     = false
}

variable "user_data" {
  description = "User data script to run on instance launch"
  type        = string
  default     = null
}

variable "ecr_repository_url" {
  description = "ECR repository URL for the service (enables ECR pull permission and SSM deploy document)"
  type        = string
  default     = null
}

variable "account_id" {
  description = "AWS account ID (used to construct IAM permissions boundary ARN)"
  type        = string
  default     = null
}

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

variable "enable_termination_protection" {
  description = "Enable EC2 instance termination protection"
  type        = bool
  default     = false
}

variable "additional_security_group_ids" {
  description = "Additional security group IDs to attach to the instance (e.g., sg-app for RDS access)"
  type        = list(string)
  default     = []
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

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
