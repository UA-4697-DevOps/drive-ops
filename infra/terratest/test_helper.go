package infratests

import (
	"path/filepath"
	"testing"

	"github.com/gruntwork-io/terratest/modules/terraform"
)

const (
	DefaultAWSRegion = "us-east-2"

	TerraformModulesPath = "../terraform/modules"

	TerragruntEnvsPath = "../terragrunt/envs"
)

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

func CreateTerraformOptions(t *testing.T, modulePath string, vars map[string]interface{}) *terraform.Options {
	t.Helper()

	// Create a unique plan file path for this test
	planFilePath := filepath.Join(t.TempDir(), "tfplan.out")

	return &terraform.Options{
		TerraformDir: modulePath,
		Vars:         vars,
		NoColor:      true,
		PlanFilePath: planFilePath,
	}
}

func VPCTestOptions(t *testing.T) *terraform.Options {
	t.Helper()
	modulePath := GetModulePath(t, "vpc")

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

func SQSTestOptions(t *testing.T, queueName string) *terraform.Options {
	t.Helper()
	modulePath := GetModulePath(t, "sqs")

	return CreateTerraformOptions(t, modulePath, map[string]interface{}{
		"project_name":       "drive-ops",
		"env":                "test",
		"cost_center":        "test",
		"queue_name":         queueName,
		"visibility_timeout": 60,
		"message_retention":  345600, // 4 days
		"max_receive_count":  3,
		"tags": map[string]string{
			"Component": "test-queue",
		},
	})
}

// SharedInfraTestOptions returns Terraform options configured for shared-infra module tests
func SharedInfraTestOptions(t *testing.T) *terraform.Options {
	t.Helper()
	modulePath := GetModulePath(t, "shared-infra")

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
	})
}

func SecretsTestOptions(t *testing.T) *terraform.Options {
	t.Helper()
	modulePath := GetModulePath(t, "secrets")

	return CreateTerraformOptions(t, modulePath, map[string]interface{}{
		"project_name":        "drive-ops",
		"env":                 "test",
		"db_identifier":       "drive-ops-test-postgres",
		"rds_master_username": "driveops_admin",
	})
}
