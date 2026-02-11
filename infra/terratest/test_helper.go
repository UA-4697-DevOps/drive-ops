// Package infratests provides test helpers and utilities for Terratest infrastructure tests.
package infratests

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/gruntwork-io/terratest/modules/terraform"
)

const (
	// DefaultAWSRegion is the default region for tests
	DefaultAWSRegion = "us-east-2"

	// TerraformModulesPath is the relative path to Terraform modules
	TerraformModulesPath = "../terraform/modules"

	// TerragruntEnvsPath is the relative path to Terragrunt environments
	TerragruntEnvsPath = "../terragrunt/envs"

	// MockProviderConfig is the HCL configuration to force offline mode
	MockProviderConfig = `
provider "aws" {
  region                      = "us-east-2"
  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true
  access_key                  = "mock_access_key"
  secret_key                  = "mock_secret_key"
}
`
)

// GetModulePath returns the absolute path to a Terraform module.
func GetModulePath(t *testing.T, moduleName string) string {
	t.Helper()
	absPath, err := filepath.Abs(filepath.Join(TerraformModulesPath, moduleName))
	if err != nil {
		t.Fatalf("Failed to get absolute path for module %s: %v", moduleName, err)
	}
	return absPath
}

// GetTerragruntPath returns the absolute path to a Terragrunt environment.
func GetTerragruntPath(t *testing.T, env, component string) string {
	t.Helper()
	absPath, err := filepath.Abs(filepath.Join(TerragruntEnvsPath, env, component))
	if err != nil {
		t.Fatalf("Failed to get absolute path for terragrunt %s/%s: %v", env, component, err)
	}
	return absPath
}

// InjectMockProvider writes a temporary provider override file to the module path.
// It returns a cleanup function that must be deferred by the caller.
func InjectMockProvider(t *testing.T, modulePath string) func() {
	t.Helper()
	filePath := filepath.Join(modulePath, "z_terratest_mock_provider_override.tf")

	err := os.WriteFile(filePath, []byte(MockProviderConfig), 0644)
	if err != nil {
		t.Fatalf("Failed to write mock provider config: %v", err)
	}

	// Return a cleanup function to remove the file after the test
	return func() {
		err := os.Remove(filePath)
		if err != nil && !os.IsNotExist(err) {
			t.Logf("WARNING: Failed to remove mock provider file %s: %v", filePath, err)
		}
	}
}

// CreateTerraformOptions creates Terraform options with the given variables.
func CreateTerraformOptions(t *testing.T, modulePath string, vars map[string]interface{}) *terraform.Options {
	t.Helper()

	// Create a unique plan file path for this test
	planFilePath := filepath.Join(t.TempDir(), "tfplan.out")

	return &terraform.Options{
		TerraformDir: modulePath,
		Vars:         vars,
		NoColor:      true,
		PlanFilePath: planFilePath,
		// We can still set these for good measure, but the override file does the real work
		EnvVars: map[string]string{
			"AWS_DEFAULT_REGION": DefaultAWSRegion,
			"AWS_REGION":         DefaultAWSRegion,
		},
	}
}

// VPCTestOptions returns Terraform options configured for VPC module tests.
func VPCTestOptions(t *testing.T) *terraform.Options {
	t.Helper()
	modulePath := GetModulePath(t, "vpc")
	
	// Inject the mock provider for VPC tests too
	cleanup := InjectMockProvider(t, modulePath)
	t.Cleanup(cleanup)

	return CreateTerraformOptions(t, modulePath, map[string]interface{}{
		"project_name": "drive-ops",
		"env":          "test",
		"vpc_cidr":     "10.0.0.0/16",
		"availability_zones": []string{
			"eu-central-1a",
			"eu-central-1b",
		},
	})
}

// SQSTestOptions returns Terraform options configured for SQS module tests.
func SQSTestOptions(t *testing.T, queueName string) *terraform.Options {
	t.Helper()
	modulePath := GetModulePath(t, "sqs")

	// Inject the mock provider for SQS tests too
	cleanup := InjectMockProvider(t, modulePath)
	t.Cleanup(cleanup)

	return CreateTerraformOptions(t, modulePath, map[string]interface{}{
		"project_name":       "drive-ops",
		"env":                "test",
		"cost_center":        "test",
		"queue_name":         queueName,
		"visibility_timeout": 60,
		"message_retention":  345600, 
		"max_receive_count":  3,
		"tags": map[string]string{
			"Component": "test-queue",
		},
	})
}
