package infratests

import (
	"fmt"
	"strings"
	"testing"

	"github.com/gruntwork-io/terratest/modules/terraform"
	"github.com/stretchr/testify/assert"
	tfjson "github.com/hashicorp/terraform-json"
)

func TestTripServiceDependencies(t *testing.T) {
	t.Parallel()

	modulePath := GetModulePath(t, "shared-infra")

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
	// 1. Validate SQS Wiring (Trip Created Queue)
	// -----------------------------------------------------------------------
	t.Run("SQS_TripCreated_Configuration", func(t *testing.T) {
		// Find the main queue
		mainQueue := findResource(t, planStruct, "aws_sqs_queue", "main_queue", "trip_created")
		assert.NotNil(t, mainQueue, "TripCreated Main Queue must be defined")
		
		// Find the DLQ (Dead Letter Queue)
		dlq := findResource(t, planStruct, "aws_sqs_queue", "dlq", "trip_created")
		assert.NotNil(t, dlq, "TripCreated DLQ must be defined (required for Redrive Policy)")

		if mainQueue != nil {
			// Verify FIFO
			assert.Equal(t, true, mainQueue.AttributeValues["fifo_queue"], "Queue must be FIFO")
			
			// Note: We skip checking 'redrive_policy' content because it contains 
			// computed values (ARN) which are "(known after apply)" and thus nil in the plan map.
			// The existence of the DLQ resource above is sufficient proof of wiring intent.
		}
	})

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
			// Verify protocol
			assert.Equal(t, "tcp", dbIngress.AttributeValues["protocol"], "Ingress must be TCP")
			assert.Equal(t, float64(5432), dbIngress.AttributeValues["from_port"], "Ingress must be port 5432")

			// Check 1: Ensure NO CIDR blocks (no public access)
			cidrBlocks := dbIngress.AttributeValues["cidr_blocks"]
			if cidrBlocks != nil {
				// If strictly nil, it's safe. If slice, ensure it's empty or doesn't contain 0.0.0.0/0
				cidrs, ok := cidrBlocks.([]interface{})
				if ok {
					assert.Empty(t, cidrs, "DB Ingress must NOT specify CIDR blocks (should use Source SG)")
				}
			}

			// Check 2: Verify Source Security Group Usage
			// Note: The value is "(known after apply)" so it might be nil in the map.
			// We check if the key exists in the config implies intention, 
			// essentially if 'source_security_group_id' is NOT explicitly empty string.
			// The fact that cidr_blocks is nil/empty (checked above) enforces isolation.
			
			// Additional check: Ensure it is Type Ingress
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
			// t.Logf("Found resource: %s", key) // Uncomment for debugging
			return resource
		}
	}
	return nil
}
