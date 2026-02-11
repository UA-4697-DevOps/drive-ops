# This file is used to bypass AWS authentication checks during Terratest runs in CI.
# It tells the AWS provider to skip all network calls to STS and Metadata services.

provider "aws" {
  region                      = "us-east-2"
  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true

  # Mock credentials to satisfy the provider's requirements
  access_key = "mock_access_key"
  secret_key = "mock_secret_key"
}
