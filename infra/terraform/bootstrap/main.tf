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

data "aws_caller_identity" "current" {}

module "external_secrets" {
  source = "../modules/external-secrets"

  project_name      = var.project_name
  env               = var.env
  aws_region        = var.aws_region
  account_id        = data.aws_caller_identity.current.account_id
  oidc_provider_arn = data.aws_iam_openid_connect_provider.eks.arn
  oidc_provider_url = replace(data.aws_eks_cluster.this.identity[0].oidc[0].issuer, "https://", "")

  tags = {
    Component = "external-secrets"
  }
}

module "eks" {
  source = "../modules/eks"

  project_name = var.project_name
  env          = var.env
  aws_region   = var.aws_region

  tags = {
    Component = "eks"
  }
}

data "aws_eks_cluster" "this" {
  name = "${var.project_name}-${var.env}-cluster"
}

data "aws_iam_openid_connect_provider" "eks" {
  url = data.aws_eks_cluster.this.identity[0].oidc[0].issuer
}
