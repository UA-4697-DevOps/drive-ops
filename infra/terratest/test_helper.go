// Package infratests provides test helpers and utilities for Terratest infrastructure tests.
package infratests

import (
	"fmt"
	"os"
	"path/filepath"
	"testing"

	"github.com/gruntwork-io/terratest/modules/files"
	"github.com/gruntwork-io/terratest/modules/terraform"
)

const (
	// DefaultAWSRegion is the default region for tests
	DefaultAWSRegion = "us-east-2"

	// TerraformModulesPath is the relative path to Terraform modules
	TerraformModulesPath = "../terraform/modules"

	// TerragruntEnvsPath is the relative path to Terragrunt environments
	TerragruntEnvsPath = "../terragrunt/envs"

	// MockProviderConfigTpl is the HCL template to force offline mode.
	// We use %s to inject the correct region dynamically.
	MockProviderConfigTpl = `
provider "aws" {
  region                      = "%s"
  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true
  access_key                  = "mock_access_key"
  secret_key                  = "mock_secret_key"
}
`
)

// GetModulePath returns the absolute path to a Terraform module source.
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

// SetupTestModule copies the ENTIRE modules directory to a temp directory
// to ensure relative paths (e.g., source = "../sqs") work correctly.
// It returns the path to the specific target module within that temp directory.
func SetupTestModule(t *testing.T, targetModuleName string, region string) string {
	t.Helper()

	// 1. Get the path to the PARENT "modules" directory
	// We need to copy everything (vpc, sqs, shared-infra) so relative paths work.
	modulesRootPath, err := filepath.Abs(TerraformModulesPath)
	if err != nil {
		t.Fatalf("Failed to resolve modules root path: %v", err)
	}

	// 2. Create a temporary directory for this test
	tempDir := t.TempDir()

	// 3. Copy the ENTIRE modules folder structure
	// This ensures that when shared-infra looks for "../sqs", it finds it in the temp dir.
	err = files.CopyFolderContents(modulesRootPath, tempDir)
	if err != nil {
		t.Fatalf("Failed to copy modules from %s to %s: %v", modulesRootPath, tempDir, err)
	}

	// 4. Determine the path to the specific module INSIDE the temp dir
	destModulePath := filepath.Join(tempDir, targetModuleName)

	// 5. Write the mock provider override file into the target module's folder
	overridePath := filepath.Join(destModulePath, "z_terratest_mock_provider_override.tf")
	configContent := fmt.Sprintf(MockProviderConfigTpl, region)

	err = os.WriteFile(overridePath, []byte(configContent), 0644)
	if err != nil {
		t.Fatalf("Failed to write mock provider config: %v", err)
	}

	// Return the path to the target module within the temp directory
	return destModulePath
}

// CreateTerraformOptions creates Terraform options with the given variables.
func CreateTerraformOptions(t *testing.T, modulePath string, vars map[string]interface{}) *terraform.Options {
	t.Helper()

	// Create a unique plan file path for this test inside the module directory
	planFilePath := filepath.Join(modulePath, "tfplan.out")

	return &terraform.Options{
		TerraformDir: modulePath,
		Vars:         vars,
		NoColor:      true,
		PlanFilePath: planFilePath,
		// We keep these EnvVars as a backup, but the override file does the main work
		EnvVars: map[string]string{
			"AWS_DEFAULT_REGION": DefaultAWSRegion,
			"AWS_REGION":         DefaultAWSRegion,
		},
	}
}

// VPCTestOptions returns Terraform options configured for VPC module tests.
func VPCTestOptions(t *testing.T) *terraform.Options {
	t.Helper()

	// FIX: Use SetupTestModule with the correct region for VPC tests (eu-central-1)
	// This resolves the "Region mismatch" warning.
	region := "eu-central-1"
	modulePath := SetupTestModule(t, "vpc", region)

	return CreateTerraformOptions(t, modulePath, map[string]interface{}{
		"project_name": "drive-ops",
		"env":          "test",
		"vpc_cidr":     "10.0.0.0/16",
		"availability_zones": []string{
			region + "a",
			region + "b",
		},
	})
}

// SQSTestOptions returns Terraform options configured for SQS module tests.
func SQSTestOptions(t *testing.T, queueName string) *terraform.Options {
	t.Helper()

	// Use default region for SQS tests
	modulePath := SetupTestModule(t, "sqs", DefaultAWSRegion)

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
