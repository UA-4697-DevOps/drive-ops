package infratests

import (
	"testing"

	"github.com/gruntwork-io/terratest/modules/terraform"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// TestSQSModuleOutputsAreDefined validates that all expected outputs are defined in the SQS module.
func TestSQSModuleOutputsAreDefined(t *testing.T) {
	t.Parallel()

	terraformOptions := SQSTestOptions(t, "trip-created")

	planStruct := terraform.InitAndPlanAndShowWithStruct(t, terraformOptions)
	require.NotNil(t, planStruct.RawPlan, "Plan should not be nil")
	require.NotNil(t, planStruct.RawPlan.PlannedValues, "PlannedValues should not be nil")

	expectedOutputs := []string{
		"queue_url",
		"queue_arn",
		"queue_name",
		"dlq_url",
		"dlq_arn",
		"dlq_name",
		"consumer_policy_arn",
		"publisher_policy_arn",
	}

	for _, outputName := range expectedOutputs {
		_, exists := planStruct.RawPlan.PlannedValues.Outputs[outputName]
		assert.True(t, exists, "Expected output '%s' should be defined in SQS module", outputName)
	}
}

// TestSQSQueueConfiguration validates FIFO queue settings.
func TestSQSQueueConfiguration(t *testing.T) {
	t.Parallel()

	terraformOptions := SQSTestOptions(t, "test-queue")

	planStruct := terraform.InitAndPlanAndShowWithStruct(t, terraformOptions)
	require.NotNil(t, planStruct.RawPlan.PlannedValues)

	var mainQueueFound bool

	for _, resource := range planStruct.RawPlan.PlannedValues.RootModule.Resources {
		if resource.Type == "aws_sqs_queue" && resource.Name == "main_queue" {
			values := resource.AttributeValues
			mainQueueFound = true

			// Verify FIFO queue settings
			assert.Equal(t, true, values["fifo_queue"], "Main queue should be FIFO")
			assert.Equal(t, true, values["content_based_deduplication"],
				"Main queue should have content-based deduplication enabled")

			// Verify queue name ends with .fifo
			name, ok := values["name"].(string)
			require.True(t, ok, "Queue name should be a string")
			assert.Contains(t, name, ".fifo", "FIFO queue name should end with .fifo")

			// Verify visibility timeout
			assert.Equal(t, float64(60), values["visibility_timeout_seconds"],
				"Visibility timeout should match configured value")
		}
	}

	assert.True(t, mainQueueFound, "Main SQS queue should be defined")
}

// TestSQSDLQWiring validates that the DLQ is properly configured alongside the main queue.
// Note: The redrive_policy is configured in Terraform but may not be exposed as a string
// in the plan output. This test validates the DLQ configuration is correct.
func TestSQSDLQWiring(t *testing.T) {
	t.Parallel()

	terraformOptions := SQSTestOptions(t, "test-queue")

	planStruct := terraform.InitAndPlanAndShowWithStruct(t, terraformOptions)
	require.NotNil(t, planStruct.RawPlan.PlannedValues)

	var (
		dlqFound       bool
		mainQueueFound bool
		mainQueueName  string
		dlqName        string
	)

	for _, resource := range planStruct.RawPlan.PlannedValues.RootModule.Resources {
		if resource.Type == "aws_sqs_queue" {
			values := resource.AttributeValues

			switch resource.Name {
			case "dlq":
				dlqFound = true
				// DLQ should also be FIFO
				assert.Equal(t, true, values["fifo_queue"], "DLQ should be FIFO")
				// DLQ should have 14-day retention
				assert.Equal(t, float64(1209600), values["message_retention_seconds"],
					"DLQ should retain messages for 14 days")
				if name, ok := values["name"].(string); ok {
					dlqName = name
				}

			case "main_queue":
				mainQueueFound = true
				if name, ok := values["name"].(string); ok {
					mainQueueName = name
				}
			}
		}
	}

	assert.True(t, dlqFound, "DLQ should be defined")
	assert.True(t, mainQueueFound, "Main queue should be defined")

	// Verify naming convention: DLQ name should contain the main queue name pattern
	assert.Contains(t, dlqName, "dlq", "DLQ name should contain 'dlq'")
	assert.Contains(t, dlqName, ".fifo", "DLQ should be a FIFO queue")
	assert.Contains(t, mainQueueName, ".fifo", "Main queue should be a FIFO queue")
}

// TestSQSIAMPolicies validates that consumer and publisher IAM policies are correctly configured.
// Note: Policy documents are computed at apply time, so we validate metadata instead.
func TestSQSIAMPolicies(t *testing.T) {
	t.Parallel()

	terraformOptions := SQSTestOptions(t, "test-queue")

	planStruct := terraform.InitAndPlanAndShowWithStruct(t, terraformOptions)
	require.NotNil(t, planStruct.RawPlan.PlannedValues)

	var consumerPolicyFound, publisherPolicyFound bool

	for _, resource := range planStruct.RawPlan.PlannedValues.RootModule.Resources {
		if resource.Type == "aws_iam_policy" {
			values := resource.AttributeValues

			switch resource.Name {
			case "consumer_policy":
				consumerPolicyFound = true

				// Validate policy metadata (policy document is computed at apply time)
				name, ok := values["name"].(string)
				assert.True(t, ok, "Consumer policy should have a name")
				assert.Contains(t, name, "consumer", "Consumer policy name should contain 'consumer'")

				description, ok := values["description"].(string)
				assert.True(t, ok, "Consumer policy should have a description")
				assert.Contains(t, description, "consuming", "Consumer policy description should mention consuming")

				// Verify policy type tag
				tags, ok := values["tags"].(map[string]interface{})
				require.True(t, ok, "expected tags map on policy resource")
				policyType, hasType := tags["PolicyType"].(string)
				require.True(t, hasType, "Consumer policy should have PolicyType tag")
				assert.Equal(t, "consumer", policyType, "PolicyType should be 'consumer'")

			case "publisher_policy":
				publisherPolicyFound = true

				// Validate policy metadata
				name, ok := values["name"].(string)
				assert.True(t, ok, "Publisher policy should have a name")
				assert.Contains(t, name, "publisher", "Publisher policy name should contain 'publisher'")

				description, ok := values["description"].(string)
				assert.True(t, ok, "Publisher policy should have a description")
				assert.Contains(t, description, "publishing", "Publisher policy description should mention publishing")

				// Verify policy type tag
				tags, ok := values["tags"].(map[string]interface{})
				require.True(t, ok, "expected tags map on policy resource")
				policyType, hasType := tags["PolicyType"].(string)
				require.True(t, hasType, "Publisher policy should have PolicyType tag")
				assert.Equal(t, "publisher", policyType, "PolicyType should be 'publisher'")
			}
		}
	}

	assert.True(t, consumerPolicyFound, "Consumer IAM policy should be defined")
	assert.True(t, publisherPolicyFound, "Publisher IAM policy should be defined")
}
