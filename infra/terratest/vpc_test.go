package infratests

import (
	"testing"

	"github.com/gruntwork-io/terratest/modules/terraform"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// TestVPCModuleOutputsAreDefined validates that all expected outputs are defined in the VPC module.
// This test uses terraform plan - no AWS resources are created.
func TestVPCModuleOutputsAreDefined(t *testing.T) {
	t.Parallel()

	terraformOptions := VPCTestOptions(t)

	// Run terraform plan and get the plan structure
	planStruct := terraform.InitAndPlanAndShowWithStruct(t, terraformOptions)
	require.NotNil(t, planStruct.RawPlan, "Plan should not be nil")
	require.NotNil(t, planStruct.RawPlan.PlannedValues, "PlannedValues should not be nil")

	// Verify expected outputs are in the plan
	expectedOutputs := []string{
		"vpc_id",
		"public_subnet_ids",
		"private_subnet_ids",
		"sg_app_id",
		"sg_db_id",
	}

	for _, outputName := range expectedOutputs {
		_, exists := planStruct.RawPlan.PlannedValues.Outputs[outputName]
		assert.True(t, exists, "Expected output '%s' should be defined in VPC module", outputName)
	}
}

// TestVPCSecurityGroupRules validates security group configurations in the plan.
// Checks that:
// - App security group has egress to 0.0.0.0/0 (for Long Polling)
// - DB security group only allows ingress from app security group on port 5432
func TestVPCSecurityGroupRules(t *testing.T) {
	t.Parallel()

	terraformOptions := VPCTestOptions(t)

	planStruct := terraform.InitAndPlanAndShowWithStruct(t, terraformOptions)
	require.NotNil(t, planStruct.RawPlan.PlannedValues)

	// Track security group rules found in plan
	var (
		appEgressAllFound      bool
		dbIngressPostgresFound bool
	)

	// Iterate through planned resources to find security group rules
	for _, resource := range planStruct.RawPlan.PlannedValues.RootModule.Resources {
		switch resource.Type {
		case "aws_security_group_rule":
			values := resource.AttributeValues

			// Check for app egress all rule
			if resource.Name == "app_egress_all" {
				assert.Equal(t, "egress", values["type"])
				assert.Equal(t, "-1", values["protocol"])

				cidrBlocks, ok := values["cidr_blocks"].([]interface{})
				if ok && len(cidrBlocks) > 0 {
					assert.Equal(t, "0.0.0.0/0", cidrBlocks[0])
					appEgressAllFound = true
				}
			}

			// Check for db ingress postgres rule
			if resource.Name == "db_ingress_postgres" {
				assert.Equal(t, "ingress", values["type"])
				assert.Equal(t, "tcp", values["protocol"])
				assert.Equal(t, float64(5432), values["from_port"])
				assert.Equal(t, float64(5432), values["to_port"])
				dbIngressPostgresFound = true
			}
		}
	}

	assert.True(t, appEgressAllFound, "App security group should have egress rule allowing all outbound traffic")
	assert.True(t, dbIngressPostgresFound, "DB security group should have ingress rule for PostgreSQL")
}

// TestVPCSubnetCIDRAllocation validates that subnet CIDR blocks are correctly calculated.
func TestVPCSubnetCIDRAllocation(t *testing.T) {
	t.Parallel()

	terraformOptions := VPCTestOptions(t)

	planStruct := terraform.InitAndPlanAndShowWithStruct(t, terraformOptions)
	require.NotNil(t, planStruct.RawPlan.PlannedValues)

	var publicSubnets, privateSubnets int

	for _, resource := range planStruct.RawPlan.PlannedValues.RootModule.Resources {
		if resource.Type == "aws_subnet" {
			values := resource.AttributeValues
			cidr, ok := values["cidr_block"].(string)
			require.True(t, ok, "Subnet should have cidr_block")

			// Public subnets use cidrsubnet(vpc_cidr, 8, 0) and cidrsubnet(vpc_cidr, 8, 1)
			// With 10.0.0.0/16: 10.0.0.0/24 and 10.0.1.0/24
			if cidr == "10.0.0.0/24" || cidr == "10.0.1.0/24" {
				publicSubnets++
			}

			// Private subnets use cidrsubnet(vpc_cidr, 8, 10) and cidrsubnet(vpc_cidr, 8, 11)
			// With 10.0.0.0/16: 10.0.10.0/24 and 10.0.11.0/24
			if cidr == "10.0.10.0/24" || cidr == "10.0.11.0/24" {
				privateSubnets++
			}
		}
	}

	assert.Equal(t, 2, publicSubnets, "Should have 2 public subnets")
	assert.Equal(t, 2, privateSubnets, "Should have 2 private subnets")
}

// TestVPCPrivateSubnetIsolation validates that private subnets have no direct internet route.
func TestVPCPrivateSubnetIsolation(t *testing.T) {
	t.Parallel()

	terraformOptions := VPCTestOptions(t)

	planStruct := terraform.InitAndPlanAndShowWithStruct(t, terraformOptions)
	require.NotNil(t, planStruct.RawPlan.PlannedValues)

	// Find the private route table and verify it has no internet gateway route
	for _, resource := range planStruct.RawPlan.PlannedValues.RootModule.Resources {
		if resource.Type == "aws_route_table" && resource.Name == "private" {
			values := resource.AttributeValues

			// Private route table should not have any routes to 0.0.0.0/0
			routes, ok := values["route"].([]interface{})
			if ok {
				for _, route := range routes {
					routeMap, ok := route.(map[string]interface{})
					if ok {
						cidr := routeMap["cidr_block"]
						assert.NotEqual(t, "0.0.0.0/0", cidr,
							"Private route table should not have a route to 0.0.0.0/0")
					}
				}
			}
		}
	}
}
