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
func SetupTestModule(t *testing.T, targetModuleName string, region string) string {
	t.Helper()

	modulesRootPath, err := filepath.Abs(TerraformModulesPath)
	if err != nil {
		t.Fatalf("Failed to resolve modules root path: %v", err)
	}

	tempDir := t.TempDir()

	err = files.CopyFolderContents(modulesRootPath, tempDir)
	if err != nil {
		t.Fatalf("Failed to copy modules from %s to %s: %v", modulesRootPath, tempDir, err)
	}

	destModulePath := filepath.Join(tempDir, targetModuleName)

	overridePath := filepath.Join(destModulePath, "z_terratest_mock_provider_override.tf")
	configContent := fmt.Sprintf(MockProviderConfigTpl, region)

	err = os.WriteFile(overridePath, []byte(configContent), 0644)
	if err != nil {
		t.Fatalf("Failed to write mock provider config: %v", err)
	}

	return destModulePath
}

// CreateTerraformOptions creates Terraform options with the given variables and region.
// Passing the region explicitly ensures that EnvVars match the Provider configuration.
func CreateTerraformOptions(t *testing.T, modulePath string, vars map[string]interface{}, region string) *terraform.Options {
	t.Helper()

	planFilePath := filepath.Join(modulePath, "tfplan.out")

	return &terraform.Options{
		TerraformDir: modulePath,
		Vars:         vars,
		NoColor:      true,
		PlanFilePath: planFilePath,
		// FIX: Use the provided region for environment variables to prevent region drift
		EnvVars: map[string]string{
			"AWS_DEFAULT_REGION": region,
			"AWS_REGION":         region,
		},
	}
}

// VPCTestOptions returns Terraform options configured for VPC module tests.
func VPCTestOptions(t *testing.T) *terraform.Options {
	t.Helper()

	// VPC module tests specifically use eu-central-1
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
	}, region)
}

// SQSTestOptions returns Terraform options configured for SQS module tests.
func SQSTestOptions(t *testing.T, queueName string) *terraform.Options {
	t.Helper()

	region := DefaultAWSRegion
	modulePath := SetupTestModule(t, "sqs", region)

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
	}, region)
}

// DriverServiceTestOptions returns Terraform options configured for Driver Service module tests.
// It points to the dev environment driver-service configuration and uses terragrunt.
func DriverServiceTestOptions(t *testing.T) *terraform.Options {
	t.Helper()

	// Locate the terragrunt configuration for driver-service in dev env
	terragruntDir := GetTerragruntPath(t, "dev", "driver-service")

	// Create a unique plan file path
	planFilePath := filepath.Join(t.TempDir(), "tfplan.out")

	return &terraform.Options{
		TerraformDir:    terragruntDir,
		TerraformBinary: "terragrunt",
		NoColor:         true,
		PlanFilePath:    planFilePath,
		// Retry common errors if needed, though for Plan it's less critical than Apply
	}
}
