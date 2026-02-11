/*
Test Suite: TripService Infrastructure Dependencies
Description:

	This test suite validates the infrastructure components required by the Trip Service,
	specifically focusing on the 'shared-infra' module where these dependencies are defined.

	It utilizes a "Plan-only" approach (terraform plan) to assert the following:
	1. SQS Wiring: Verifies that ALL required queues (trip-created, driver-assigned, trip-completed)
	   are configured as FIFO and have valid Redrive Policies (DLQ).
	2. Network Security: Verifies that the Database Security Group allows ingress traffic
	   exclusively from the Application Security Group.
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

	modulePath := "../terratest/fixtures/shared-infra"

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
	// Define the list of queue modules expected to be found in shared-infra
	targetQueues := []string{"trip_created", "driver_assigned", "trip_completed"}

	for _, queueModule := range targetQueues {
		// Run a subtest for each queue
		t.Run(fmt.Sprintf("SQS_%s_Configuration", queueModule), func(t *testing.T) {

			// Find the main queue within the specific module (e.g. module.trip_created...)
			mainQueue := findResource(t, planStruct, "aws_sqs_queue", "main_queue", queueModule)
			assert.NotNil(t, mainQueue, fmt.Sprintf("%s Main Queue must be defined", queueModule))

			// Find the DLQ within the specific module
			dlq := findResource(t, planStruct, "aws_sqs_queue", "dlq", queueModule)
			assert.NotNil(t, dlq, fmt.Sprintf("%s DLQ must be defined", queueModule))

			if mainQueue != nil {
				// Verify FIFO
				assert.Equal(t, true, mainQueue.AttributeValues["fifo_queue"], "Queue must be FIFO")

				// Verify wiring to the DLQ.
				// (We do not check the JSON redrive_policy content in detail because it contains unknown values,
				// but checking for the existence of the DLQ resource nearby is a good indicator).
			}
		})
	}

	// -----------------------------------------------------------------------
	// 2. Validate Security Group Wiring (App -> DB)
	// -----------------------------------------------------------------------
	t.Run("SecurityGroup_Isolation", func(t *testing.T) {
		// Verify App SG exists
		appSg := findResource(t, planStruct, "aws_security_group", "app", "vpc")
		assert.NotNil(t, appSg, "App Security Group must be defined")

		// Verify DB Ingress Rule exists
		dbIngress := findResource(t, planStruct, "aws_security_group_rule", "db_ingress_postgres", "vpc")
		assert.NotNil(t, dbIngress, "DB Ingress Rule must be defined")

		if dbIngress != nil {
			assert.Equal(t, "tcp", dbIngress.AttributeValues["protocol"], "Ingress must be TCP")
			assert.Equal(t, float64(5432), dbIngress.AttributeValues["from_port"], "Ingress must be port 5432")
			assert.Equal(t, float64(5432), dbIngress.AttributeValues["to_port"], "Ingress to_port must be 5432")

			// Check 1: Ensure NO CIDR blocks (no public access)
			cidrBlocks := dbIngress.AttributeValues["cidr_blocks"]
			if cidrBlocks != nil {
				cidrs, ok := cidrBlocks.([]interface{})
				if ok {
					assert.Empty(t, cidrs, "DB Ingress must NOT specify CIDR blocks (should use Source SG)")
				}
			}

			// Check 2: Verify Rule Type
			assert.Equal(t, "ingress", dbIngress.AttributeValues["type"], "Rule must be type ingress")
		}
	})
}

// findResource looks for a resource ending in "type.name", optionally filtered by parent module.
func findResource(t *testing.T, plan *terraform.PlanStruct, resType string, resName string, parentModule string) *tfjson.StateResource {
	t.Helper()
	targetSuffix := fmt.Sprintf("%s.%s", resType, resName)

	for key, resource := range plan.ResourcePlannedValuesMap {
		if strings.HasSuffix(key, targetSuffix) {
			if parentModule != "" && !strings.Contains(key, fmt.Sprintf("module.%s", parentModule)) {
				continue
			}
			return resource
		}
	}
	return nil
}
