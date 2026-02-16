package infratests

import (
	"fmt"
	"strings"
	"testing"

	"github.com/gruntwork-io/terratest/modules/terraform"
	tfjson "github.com/hashicorp/terraform-json"
	"github.com/stretchr/testify/assert"
)

func TestDriverServiceInfra(t *testing.T) {
	t.Parallel()

	region := "us-east-2"

	// 1. Setup the test module in a temp directory with a mock provider.
	modulePath := SetupTestModule(t, "shared-infra", region)

	// 2. Create Terraform options.
	terraformOptions := CreateTerraformOptions(t, modulePath, map[string]interface{}{
		"project_name":                       "drive-ops",
		"env":                                "test",
		"account_id":                         "123456789012",
		"cost_center":                        "test-center",
		"vpc_cidr":                           "10.0.0.0/16",
		"availability_zones":                 []string{region + "a", region + "b"},
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
	}, region)

	planStruct := terraform.InitAndPlanAndShowWithStruct(t, terraformOptions)

	// -----------------------------------------------------------------------
	// 1. Validate SQS Wiring (Driver Service Queues)
	// -----------------------------------------------------------------------
	// DriverService consumes trip_created and produces driver_assigned
	targetQueues := []string{"trip_created", "driver_assigned"}

	for _, queueModule := range targetQueues {
		t.Run(fmt.Sprintf("SQS_%s_Configuration", queueModule), func(t *testing.T) {

			// Use findDriverResourceChange to inspect planned changes (supports computed values)
			mainQueue := findDriverResourceChange(t, planStruct, "aws_sqs_queue", "main_queue", queueModule)
			assert.NotNil(t, mainQueue, fmt.Sprintf("%s Main Queue must be defined", queueModule))

			dlq := findDriverResourceChange(t, planStruct, "aws_sqs_queue", "dlq", queueModule)
			assert.NotNil(t, dlq, fmt.Sprintf("%s DLQ must be defined", queueModule))

			if mainQueue != nil {
				// Access known values map
				props := mainQueue.Change.After.(map[string]interface{})
				assert.Equal(t, true, props["fifo_queue"], "Queue must be FIFO")

				// Robust check for Redrive Policy (handles "known after apply")
				policyVal, isKnown := props["redrive_policy"]

				unknowns := mainQueue.Change.AfterUnknown.(map[string]interface{})
				_, isComputed := unknowns["redrive_policy"]

				if isKnown && policyVal != nil {
					policyStr := policyVal.(string)
					assert.Contains(t, policyStr, "\"maxReceiveCount\"", "Policy must specify maxReceiveCount")
				} else if isComputed {
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
		appSg := findDriverResourceChange(t, planStruct, "aws_security_group", "app", "vpc")
		assert.NotNil(t, appSg, "App Security Group must be defined")

		dbSg := findDriverResourceChange(t, planStruct, "aws_security_group", "db", "vpc")
		assert.NotNil(t, dbSg, "DB Security Group must be defined")

		dbIngress := findDriverResourceChange(t, planStruct, "aws_security_group_rule", "db_ingress_postgres", "vpc")
		assert.NotNil(t, dbIngress, "DB Ingress Rule must be defined")

		if dbIngress != nil {
			props := dbIngress.Change.After.(map[string]interface{})

			assert.Equal(t, "tcp", props["protocol"], "Ingress must be TCP")
			assert.Equal(t, float64(5432), props["from_port"], "Ingress must be port 5432")
			assert.Equal(t, float64(5432), props["to_port"], "Ingress to_port must be 5432")
			assert.Equal(t, "ingress", props["type"], "Rule must be type ingress")
		}
	})
}

func findDriverResourceChange(t *testing.T, plan *terraform.PlanStruct, resType string, resName string, parentModule string) *tfjson.ResourceChange {
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
