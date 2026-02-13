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
	DefaultAWSRegion = "us-east-2"

	TerraformModulesPath = "../terraform/modules"

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
// It automatically adds environment variables to force offline/mock mode for AWS,
// matching the configuration used in CI/CD.
func CreateTerraformOptions(t *testing.T, modulePath string, vars map[string]interface{}, region string) *terraform.Options {
	t.Helper()

	planFilePath := filepath.Join(modulePath, "tfplan.out")

	return &terraform.Options{
		TerraformDir: modulePath,
		Vars:         vars,
		NoColor:      true,
		PlanFilePath: planFilePath,
		
		// Centralized environment variables for offline testing.
		// These prevent Terraform from attempting to contact real AWS STS/Metadata APIs.
		EnvVars: map[string]string{
			"AWS_DEFAULT_REGION":              region,
			"AWS_REGION":                      region,
			"AWS_ACCESS_KEY_ID":               "testing",
			"AWS_SECRET_ACCESS_KEY":           "testing",
			"AWS_SKIP_CREDENTIALS_VALIDATION": "true",
			"AWS_SKIP_REQUESTING_ACCOUNT_ID":  "true",
			"AWS_SKIP_METADATA_API_CHECK":     "true",
			"AWS_SKIP_REGION_CHECK":           "true",
			"AWS_EC2_METADATA_DISABLED":       "true",
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
		"account_id":   "123456789012",
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

// SharedInfraTestOptions returns Terraform options configured for shared-infra module tests
func SharedInfraTestOptions(t *testing.T) *terraform.Options {
	t.Helper()
	region := DefaultAWSRegion
	modulePath := SetupTestModule(t, "shared-infra", region)

	return CreateTerraformOptions(t, modulePath, map[string]interface{}{
		"project_name": "drive-ops",
		"env":          "test",
		"cost_center":  "test",
		"account_id":   "123456789012", // Dummy account ID for testing

		"vpc_cidr":           "10.0.0.0/16",
		"availability_zones": []string{"us-east-2a", "us-east-2b"},

		// VPC Flow Logs
		"enable_flow_logs":           false, // Disabled for tests
		"flow_log_retention_in_days": 1,

		// SQS settings
		"enable_ha":         false,
		"message_retention": 345600, // 4 days
		"max_receive_count": 3,

		"trip_created_visibility_timeout":    60,
		"driver_assigned_visibility_timeout": 60,
		"trip_completed_visibility_timeout":  60,

		"common_tags": map[string]string{
			"Module": "shared-infra-test",
			"Owner":  "DevOps Team",
		},
	}, region)
}

func SecretsTestOptions(t *testing.T) *terraform.Options {
	t.Helper()
	region := DefaultAWSRegion
	modulePath := SetupTestModule(t, "secrets", region)

	return CreateTerraformOptions(t, modulePath, map[string]interface{}{
		"project_name":        "drive-ops",
		"env":                 "test",
		"db_identifier":       "drive-ops-test-postgres",
		"rds_master_username": "driveops_admin",
	}, region)
}
