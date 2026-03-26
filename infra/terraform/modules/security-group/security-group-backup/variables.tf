# ==============================================================================
# SECURITY GROUP MODULE – VARIABLES
# ==============================================================================

variable "name" {
  description = "Name of the security group (used for both resource name and Name tag)"
  type        = string
}

variable "description" {
  description = "Description of the security group"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID where the security group will be created"
  type        = string
}

variable "ingress_rules" {
  description = <<-EOT
    List of ingress rules. Each rule must have:
      - key:         unique identifier for the rule (used in for_each)
      - from_port:   start of port range
      - to_port:     end of port range
      - protocol:    tcp, udp, or -1 (all)
      - cidr_blocks: list of CIDR blocks
      - description: human-readable description
  EOT

  type = list(object({
    key         = string
    from_port   = number
    to_port     = number
    protocol    = string
    cidr_blocks = list(string)
    description = optional(string, "")
  }))

  default = []
}

variable "egress_rules" {
  description = <<-EOT
    List of egress rules. Each rule must have:
      - key:         unique identifier for the rule (used in for_each)
      - from_port:   start of port range
      - to_port:     end of port range
      - protocol:    tcp, udp, or -1 (all)
      - cidr_blocks: list of CIDR blocks
      - description: human-readable description
  EOT

  type = list(object({
    key         = string
    from_port   = number
    to_port     = number
    protocol    = string
    cidr_blocks = list(string)
    description = optional(string, "")
  }))

  default = []
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
