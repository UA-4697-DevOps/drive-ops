# ==============================================================================
# KARPENTER TERRAGRUNT – DEV ENVIRONMENT
# ==============================================================================
# Deploys Karpenter as an experimental alternative to Cluster Autoscaler.
#
# Prerequisites:
#   1. EKS cluster must be running:         cd ../eks && terragrunt apply
#   2. AWS LB Controller must be deployed:  cd ../aws-lb-controller && terragrunt apply
#
# Usage:
#   cd infra/terragrunt/envs/dev/karpenter
#   terragrunt plan
#   terragrunt apply
#
# Post-apply:
#   ArgoCD will sync EC2NodeClass + NodePool from:
#   infra/k8s/manifests/karpenter/
#
# Verify:
#   kubectl get pods -n kube-system -l app.kubernetes.io/name=karpenter
# ==============================================================================

include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  source = "../../../../terraform//modules/karpenter"
}

locals {
  common_vars = yamldecode(file(find_in_parent_folders("common_vars.yaml")))
  env_vars    = yamldecode(file(find_in_parent_folders("env_vars.yaml")))
}

dependency "eks" {
  config_path = "../eks"

  mock_outputs_allowed_terraform_commands = ["validate", "plan", "init", "destroy"]
  mock_outputs_merge_strategy_with_state  = "shallow"

  mock_outputs = {
    oidc_provider_arn = "arn:aws:iam::123456789012:oidc-provider/mock"
    oidc_provider_url = "oidc.eks.us-east-2.amazonaws.com/id/mock"
    cluster_name      = "mock-cluster"
    node_role_arn     = "arn:aws:iam::123456789012:role/mock-node-role"
  }
}

inputs = {
  project_name      = local.common_vars.project_name
  env               = local.env_vars.env
  account_id        = local.env_vars.account_id
  aws_region        = try(local.env_vars.aws_region, local.common_vars.aws_region)
  cluster_name      = dependency.eks.outputs.cluster_name
  oidc_provider_arn = dependency.eks.outputs.oidc_provider_arn
  oidc_provider_url = dependency.eks.outputs.oidc_provider_url
  node_role_arn     = dependency.eks.outputs.node_role_arn

  karpenter_version = "1.3.3"

  tags = {
    Component  = "karpenter"
    Experiment = "true"
  }
}
