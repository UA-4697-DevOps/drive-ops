data "aws_ssm_parameter" "al2023_ami" {
  count = var.ami == null ? 1 : 0
  name  = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

locals {
  resolved_ami = var.ami != null ? var.ami : data.aws_ssm_parameter.al2023_ami[0].value
}
