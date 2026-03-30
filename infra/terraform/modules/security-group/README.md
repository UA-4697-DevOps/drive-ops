# Security Group Shared Module

Generic reusable module for managing AWS Security Groups with dynamic ingress and egress rules.

## Usage

```hcl
module "sg" {
  source      = "../security-group"
  name        = "example-sg"
  description = "Example description"
  vpc_id      = var.vpc_id

  ingress_rules = [
    {
      key         = "http"
      from_port   = 80
      to_port     = 80
      protocol    = "tcp"
      cidr_blocks = ["0.0.0.0/0"]
    }
  ]

  tags = var.tags
}
```
