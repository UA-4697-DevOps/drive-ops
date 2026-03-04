terraform {
  required_version = ">= 1.2.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "6.28.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.env
      ManagedBy   = "Terraform"
      CostCenter  = var.cost_center
    }
  }
}

module "state_backend" {
  source = "../modules/state-backend"

  project_name = var.project_name
  env          = var.env
  cost_center  = var.cost_center

  state_bucket_name = "${var.project_name}-${var.env}-terraform-state"
  lock_table_name   = "${var.project_name}-${var.env}-terraform-locks"

  tags = {
    Component = "state-backend"
  }
}

module "external_secrets" {
  source = "../modules/external-secrets"

  project_name      = var.project_name
  env               = var.env
  aws_region        = var.aws_region
  account_id        = "969283154407"
  oidc_provider_arn = module.eks.oidc_provider_arn
  oidc_provider_url = module.eks.oidc_provider_url

  tags = {
    Component = "external-secrets"
  }
}
