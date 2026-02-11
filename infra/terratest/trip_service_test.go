/*
Test Suite: TripService Infrastructure Dependencies
Description:
    This test suite validates the infrastructure components required by the Trip Service.
    It uses 'ResourceChangesMap' to handle computed values (like ARNs) correctly in a Plan-only test.
*/
package infratests

import (
	"fmt"
	"strings"
	"testing"

	"github.com/gruntwork-io/terratest/modules/terraform"
	tfjson "github.com/hashicorp/terraform-json"
	"github.com/stretchr/testify/assert"
)

func TestTripServiceDependencies(t *testing.T) {
	t.Parallel()

	modulePath := SetupTestModule(t, "shared-infra", "us-east-2")

	terraformOptions := CreateTerraformOptions(t, modulePath, map[string]interface{}{
		"project_name":                       "drive-ops",
		"env":                                "test",
		"account_id":                         "123456789012",
		"cost_center":                        "test-center",
		"vpc_cidr":                           "10.0.0.0/16",
		"availability_zones":                 []string{"us-east-2a", "us-east-2b"},
		"enable_flow_logs":                   false,
		"flow_log_retention_in_days":         1,
		"enable_ha":                          false,
		"message_retention":                  345600,
		"max_receive_count":                  3,
		"trip_created_visibility_timeout":    60,
		"driver_assigned_visibility_timeout": 60,
		"trip_completed_visibility_timeout":  60,
		"common_tags": map[string]string{
			"Test": "true",
		},
	})

	planStruct := terraform.InitAndPlanAndShowWithStruct(t, terraformOptions)

	// -----------------------------------------------------------------------
	// 1. Validate SQS Wiring (All Service Queues)
	// -----------------------------------------------------------------------
	targetQueues := []string{"trip_created", "driver_assigned", "trip_completed"}

	for _, queueModule := range targetQueues {
		t.Run(fmt.Sprintf("SQS_%s_Configuration", queueModule), func(t *testing.T) {

			// Use findResourceChange to inspect planned changes (supports computed values)
			mainQueue := findResourceChange(t, planStruct, "aws_sqs_queue", "main_queue", queueModule)
			assert.NotNil(t, mainQueue, fmt.Sprintf("%s Main Queue must be defined", queueModule))

			dlq := findResourceChange(t, planStruct, "aws_sqs_queue", "dlq", queueModule)
			assert.NotNil(t, dlq, fmt.Sprintf("%s DLQ must be defined", queueModule))

			if mainQueue != nil {
				// Access known values map
				props := mainQueue.Change.After.(map[string]interface{})
				assert.Equal(t, true, props["fifo_queue"], "Queue must be FIFO")

				// FIX: Robust check for Redrive Policy (handles "known after apply")
				// Check if the value is known (static)
				policyVal, isKnown := props["redrive_policy"]
				
				// Check if the value is computed (unknown/known after apply)
				unknowns := mainQueue.Change.AfterUnknown.(map[string]interface{})
				_, isComputed := unknowns["redrive_policy"]

				// It must be either explicitly set OR computed. If both are missing/nil, wiring is broken.
				if isKnown && policyVal != nil {
					// If strictly known, we can check the string
					policyStr := policyVal.(string)
					assert.Contains(t, policyStr, "\"maxReceiveCount\"", "Policy must specify maxReceiveCount")
				} else if isComputed {
					// If computed, it means Terraform sees the link to DLQ ARN.
					// This is a PASS for a plan-only test.
					t.Logf("SQS %s: Redrive policy is correctly wired (computed from DLQ ARN).", queueModule)
				} else {
					assert.Fail(t, "Redrive Policy is missing or nil (not linked to DLQ)", "Queue: %s", queueModule)
				}
			}
		})
	}

	// -----------------------------------------------------------------------
	// 2. Validate Security Group Wiring (App -> DB)
	// -----------------------------------------------------------------------
	t.Run("SecurityGroup_Isolation", func(t *testing.T) {
		appSg := findResourceChange(t, planStruct, "aws_security_group", "app", "vpc")
		assert.NotNil(t, appSg, "App Security Group must be defined")

		dbIngress := findResourceChange(t, planStruct, "aws_security_group_rule", "db_ingress_postgres", "vpc")
		assert.NotNil(t, dbIngress, "DB Ingress Rule must be defined")

		if dbIngress != nil {
			props := dbIngress.Change.After.(map[string]interface{})
			
			assert.Equal(t, "tcp", props["protocol"], "Ingress must be TCP")
			assert.Equal(t, float64(5432), props["from_port"], "Ingress must be port 5432")
			assert.Equal(t, float64(5432), props["to_port"], "Ingress to_port must be 5432")

			cidrBlocks := props["cidr_blocks"]
			if cidrBlocks != nil {
				cidrs, ok := cidrBlocks.([]interface{})
				if ok {
					assert.Empty(t, cidrs, "DB Ingress must NOT specify CIDR blocks (should use Source SG)")
				}
			}
			assert.Equal(t, "ingress", props["type"], "Rule must be type ingress")
		}
	})
}

// Updated helper: returns ResourceChange instead of StateResource
// This allows access to 'AfterUnknown' for computed attributes.
func findResourceChange(t *testing.T, plan *terraform.PlanStruct, resType string, resName string, parentModule string) *tfjson.ResourceChange {
	t.Helper()
	targetSuffix := fmt.Sprintf("%s.%s", resType, resName)

	for key, resource := range plan.ResourceChangesMap {
		if strings.HasSuffix(key, targetSuffix) {
			if parentModule != "" && !strings.Contains(key, fmt.Sprintf("module.%s", parentModule)) {
				continue
			}
			return resource
		}
	}
	return nil
}
