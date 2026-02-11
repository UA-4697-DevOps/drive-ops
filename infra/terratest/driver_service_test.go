package infratests

import (
	"testing"

	"github.com/gruntwork-io/terratest/modules/terraform"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestDriverServiceInfra(t *testing.T) {
	t.Parallel()

	terraformOptions := DriverServiceTestOptions(t)

	// Clean up after the test (though strictly for Plan it doesn't create resources,
	// good practice if we switch to Apply later)
	// defer terraform.Destroy(t, terraformOptions)

	// Run Init and Plan, then parse the plan output
	// Note: We use InitAndPlanAndShowWithStruct to get a structured representation of the plan
	planStruct := terraform.InitAndPlanAndShowWithStruct(t, terraformOptions)

	require.NotNil(t, planStruct.RawPlan, "Plan should not be nil")
	require.NotNil(t, planStruct.RawPlan.PlannedValues, "PlannedValues should not be nil")

	// Validate resources
	var ecrRepoFound bool

	for _, resource := range planStruct.RawPlan.PlannedValues.RootModule.Resources {
		if resource.Type == "aws_ecr_repository" && resource.Name == "service_repository" {
			ecrRepoFound = true

			values := resource.AttributeValues

			// Verify repository name
			repoName, ok := values["name"].(string)
			assert.True(t, ok, "Repository name should be a string")
			assert.Equal(t, "driver-service", repoName, "Repository name should match inputs")

			// Verify tags (checking if Common Tags are applied)
			// Note: Terraform AWS provider puts merged tags (resource tags + provider default tags) in tags_all
			tags, ok := values["tags_all"].(map[string]interface{})
			if assert.True(t, ok, "Tags should be a map") {
				assert.Equal(t, "drive-ops", tags["Project"], "Should have Project tag")
				assert.Equal(t, "Terragrunt", tags["ManagedBy"], "Should have ManagedBy tag")
			}
		}
	}

	assert.True(t, ecrRepoFound, "ECR repository resource should be defined")
}
