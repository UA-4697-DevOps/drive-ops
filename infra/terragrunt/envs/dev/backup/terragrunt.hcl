include "root" {
  path = find_in_parent_folders("root.hcl")
}

# Point to the actual Terraform module we discussed earlier
terraform {
  source = "../../../../terraform/modules//backup" # Keep repo context so sibling modules like ../iam-role are available
}

# Pull in the outputs from your EKS cluster
dependency "eks" {
  config_path = "../eks"

  # Mocks are helpful if you run a plan on everything before EKS is built
  mock_outputs = {
    oidc_provider_arn = "arn:aws:iam::111122223333:oidc-provider/oidc.eks.us-east-2.amazonaws.com/id/MOCK"
    oidc_provider_url = "https://oidc.eks.us-east-2.amazonaws.com/id/MOCK"
  }
}

inputs = {
  # Pass the EKS dependency outputs into the backup module's variables
  eks_oidc_provider_arn = dependency.eks.outputs.oidc_provider_arn
  eks_oidc_provider_url = dependency.eks.outputs.oidc_provider_url

  # Kubernetes details for the IAM Role (IRSA)
  k8s_namespace            = "default"
  k8s_service_account_name = "db-backup-sa"

  # NEW: KMS Key for S3 Encryption (Using AWS-managed key to satisfy CodeRabbit review)
  backup_kms_key_arn = "alias/aws/s3"
}
