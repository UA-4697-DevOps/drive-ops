// Package infratests provides test helpers and utilities for Terratest infrastructure tests.
package infratests

import (
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

// CreateTerraformOptions creates Terraform options with the given variables.
// This is a generic helper that only passes the variables you provide.
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

// VPCTestOptions returns Terraform options configured for VPC module tests.
// Variables: project_name, env, vpc_cidr, availability_zones
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

// SQSTestOptions returns Terraform options configured for SQS module tests.
// Variables: project_name, env, cost_center, queue_name, visibility_timeout, max_receive_count, tags
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
