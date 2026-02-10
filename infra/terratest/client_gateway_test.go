package infratests

import (
	"testing"

	"github.com/gruntwork-io/terratest/modules/terraform"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestClientGatewaySharedInfraOutputs(t *testing.T) {
	t.Parallel()

	terraformOptions := SharedInfraTestOptions(t)
	planStruct := terraform.InitAndPlanAndShowWithStruct(t, terraformOptions)

	require.NotNil(t, planStruct.RawPlan, "Plan should not be nil")
	require.NotNil(t, planStruct.RawPlan.PlannedValues, "PlannedValues should not be nil")

	// ClientGateway requires these outputs from shared-infra
	expectedOutputs := []string{
		// VPC outputs for network connectivity
		"vpc_id",
		"public_subnet_ids",
		"private_subnet_ids",
		"sg_app_id",

		// SQS outputs for driver command queues
		"driver_assigned_queue_url",
		"trip_completed_queue_url",
		"all_queue_arns",
		"all_dlq_arns",
	}

	for _, outputName := range expectedOutputs {
		_, exists := planStruct.RawPlan.PlannedValues.Outputs[outputName]
		assert.True(t, exists, "Expected output '%s' should be defined for ClientGateway", outputName)
	}
}

func TestClientGatewaySecurityGroupAllowsOutbound(t *testing.T) {
	t.Parallel()

	terraformOptions := VPCTestOptions(t)
	planStruct := terraform.InitAndPlanAndShowWithStruct(t, terraformOptions)
	require.NotNil(t, planStruct.RawPlan.PlannedValues)

	var outboundRuleFound bool

	for _, resource := range planStruct.RawPlan.PlannedValues.RootModule.Resources {
		if resource.Type == "aws_security_group_rule" && resource.Name == "app_egress_all" {
			values := resource.AttributeValues
			outboundRuleFound = true

			// Verify egress rule configuration
			assert.Equal(t, "egress", values["type"], "Rule should be egress type")
			assert.Equal(t, float64(0), values["from_port"], "Should allow all ports (from 0)")
			assert.Equal(t, float64(0), values["to_port"], "Should allow all ports (to 0)")
			assert.Equal(t, "-1", values["protocol"], "Should allow all protocols")

			// Verify it allows all destinations (required for Telegram API)
			cidrBlocks, ok := values["cidr_blocks"].([]interface{})
			require.True(t, ok, "cidr_blocks should be a list")
			assert.Contains(t, cidrBlocks, "0.0.0.0/0", "Should allow outbound to any destination")

			// Verify description mentions Long Polling
			description, ok := values["description"].(string)
			require.True(t, ok, "Description should be a string")
			assert.Contains(t, description, "Long Polling", "Description should mention Long Polling requirement")
		}
	}

	assert.True(t, outboundRuleFound, "App security group should have outbound rule for Telegram Bot API")
}

func TestClientGatewaySQSQueuesConfiguration(t *testing.T) {
	t.Parallel()

	terraformOptions := SharedInfraTestOptions(t)
	planStruct := terraform.InitAndPlanAndShowWithStruct(t, terraformOptions)

	require.NotNil(t, planStruct.RawPlan.PlannedValues)

	// Track which queues we found
	queuesFound := make(map[string]bool)
	expectedQueues := []string{"driver_assigned", "trip_completed"}

	// Check module outputs for queue URLs
	outputs := planStruct.RawPlan.PlannedValues.Outputs

	for _, queueName := range expectedQueues {
		outputKey := queueName + "_queue_url"
		_, exists := outputs[outputKey]
		queuesFound[queueName] = exists
	}

	// Verify all expected queues are present
	for _, queueName := range expectedQueues {
		assert.True(t, queuesFound[queueName],
			"ClientGateway requires '%s' queue to be configured", queueName)
	}

	// Verify DLQ outputs exist
	_, dlqOutputExists := outputs["all_dlq_arns"]
	assert.True(t, dlqOutputExists, "DLQ configuration should be available for all queues")
}

func TestClientGatewaySecretsOutputs(t *testing.T) {
	t.Parallel()

	terraformOptions := SecretsTestOptions(t)
	planStruct := terraform.InitAndPlanAndShowWithStruct(t, terraformOptions)

	require.NotNil(t, planStruct.RawPlan, "Plan should not be nil")
	require.NotNil(t, planStruct.RawPlan.PlannedValues, "PlannedValues should not be nil")

	// Check for secrets outputs
	expectedOutputs := []string{
		"rds_master_secret_arn",
		"rds_master_secret_name",
	}

	for _, outputName := range expectedOutputs {
		_, exists := planStruct.RawPlan.PlannedValues.Outputs[outputName]
		assert.True(t, exists, "Expected secrets output '%s' should be defined", outputName)
	}
}

func TestClientGatewayNetworkingSetup(t *testing.T) {
	t.Parallel()

	terraformOptions := VPCTestOptions(t)
	planStruct := terraform.InitAndPlanAndShowWithStruct(t, terraformOptions)

	require.NotNil(t, planStruct.RawPlan.PlannedValues)

	var (
		vpcFound           bool
		publicSubnetFound  bool
		privateSubnetFound bool
		igwFound           bool
	)

	for _, resource := range planStruct.RawPlan.PlannedValues.RootModule.Resources {
		switch resource.Type {
		case "aws_vpc":
			if resource.Name == "main" {
				vpcFound = true
			}

		case "aws_subnet":
			values := resource.AttributeValues
			tags, ok := values["tags"].(map[string]interface{})
			if !ok {
				continue
			}

			// Check if the subnet name contains "public" or "private"
			name, hasName := tags["Name"]
			if !hasName {
				continue
			}

			nameStr, ok := name.(string)
			if !ok {
				continue
			}

			if containsIgnoreCase(nameStr, "public") {
				publicSubnetFound = true
			} else if containsIgnoreCase(nameStr, "private") {
				privateSubnetFound = true
			}

		case "aws_internet_gateway":
			igwFound = true
		}
	}

	assert.True(t, vpcFound, "VPC should be defined for ClientGateway networking")
	assert.True(t, publicSubnetFound, "Public subnet should exist for internet connectivity")
	assert.True(t, privateSubnetFound, "Private subnet should exist for app layer")
	assert.True(t, igwFound, "Internet Gateway should exist for outbound connectivity")
}

// containsIgnoreCase checks if a string contains a substring (case-insensitive)
func containsIgnoreCase(str, substr string) bool {
	str = toLower(str)
	substr = toLower(substr)
	return contains(str, substr)
}

// toLower converts a string to lowercase
func toLower(str string) string {
	result := ""
	for _, r := range str {
		if r >= 'A' && r <= 'Z' {
			result += string(r + 32)
		} else {
			result += string(r)
		}
	}
	return result
}

// contains checks if a string contains a substring
func contains(str, substr string) bool {
	if len(substr) == 0 {
		return true
	}
	if len(str) < len(substr) {
		return false
	}
	for i := 0; i <= len(str)-len(substr); i++ {
		if str[i:i+len(substr)] == substr {
			return true
		}
	}
	return false
}
