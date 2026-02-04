package infratests

import (
	"testing"

	"github.com/gruntwork-io/terratest/modules/terraform"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// TestRDSSecurityGroupRules validates that RDS-related security group rules are correctly configured.
// This test checks the VPC module's security groups that would protect RDS instances.
//
// The test validates:
// - DB security group only allows ingress on port 5432 (PostgreSQL)
// - Ingress is only allowed from the app security group (not from 0.0.0.0/0)
func TestRDSSecurityGroupRules(t *testing.T) {
	t.Parallel()

	terraformOptions := VPCTestOptions(t)

	planStruct := terraform.InitAndPlanAndShowWithStruct(t, terraformOptions)
	require.NotNil(t, planStruct.RawPlan.PlannedValues)

	var (
		dbSecurityGroupFound bool
		dbIngressRuleFound   bool
		noPublicIngressToDB  = true
	)

	for _, resource := range planStruct.RawPlan.PlannedValues.RootModule.Resources {
		switch resource.Type {
		case "aws_security_group":
			if resource.Name == "db" {
				dbSecurityGroupFound = true
				values := resource.AttributeValues

				// Verify the security group is for RDS
				description, ok := values["description"].(string)
				if ok {
					assert.Contains(t, description, "RDS",
						"DB security group description should mention RDS")
				}
			}

		case "aws_security_group_rule":
			values := resource.AttributeValues

			// Check for PostgreSQL ingress rule
			if resource.Name == "db_ingress_postgres" {
				dbIngressRuleFound = true

				// Verify it's an ingress rule
				assert.Equal(t, "ingress", values["type"],
					"DB ingress rule should be of type 'ingress'")

				// Verify correct port
				assert.Equal(t, float64(5432), values["from_port"],
					"DB ingress should allow from port 5432")
				assert.Equal(t, float64(5432), values["to_port"],
					"DB ingress should allow to port 5432")

				// Verify protocol is TCP
				assert.Equal(t, "tcp", values["protocol"],
					"DB ingress should use TCP protocol")

				// Verify it references a source security group (not CIDR)
				// The presence of source_security_group_id without cidr_blocks
				// means traffic is restricted to the app layer only
				cidrBlocks, hasCIDR := values["cidr_blocks"]
				if hasCIDR && cidrBlocks != nil {
					cidrList, ok := cidrBlocks.([]interface{})
					if ok {
						for _, cidr := range cidrList {
							if cidr == "0.0.0.0/0" {
								noPublicIngressToDB = false
							}
						}
					}
				}
			}
		}
	}

	assert.True(t, dbSecurityGroupFound, "DB security group should be defined")
	assert.True(t, dbIngressRuleFound, "PostgreSQL ingress rule should be defined for DB security group")
	assert.True(t, noPublicIngressToDB, "DB security group should NOT allow ingress from 0.0.0.0/0")
}

// TestRDSSubnetPlacement validates that RDS would be placed in private subnets.
// This test verifies that private subnets exist and are isolated from the internet.
func TestRDSSubnetPlacement(t *testing.T) {
	t.Parallel()

	terraformOptions := VPCTestOptions(t)

	planStruct := terraform.InitAndPlanAndShowWithStruct(t, terraformOptions)
	require.NotNil(t, planStruct.RawPlan.PlannedValues)

	var privateSubnetCount int

	for _, resource := range planStruct.RawPlan.PlannedValues.RootModule.Resources {
		if resource.Type == "aws_subnet" {
			values := resource.AttributeValues

			// Check if this is a private subnet (by checking map_public_ip_on_launch)
			mapPublicIP, ok := values["map_public_ip_on_launch"].(bool)
			if ok && !mapPublicIP {
				privateSubnetCount++

				// Verify private subnet tags contain "private"
				tags, ok := values["tags"].(map[string]interface{})
				if ok {
					name, hasName := tags["Name"].(string)
					if hasName {
						assert.Contains(t, name, "private",
							"Private subnet name should contain 'private'")
					}
				}
			}
		}
	}

	assert.GreaterOrEqual(t, privateSubnetCount, 2,
		"Should have at least 2 private subnets for RDS multi-AZ deployment")
}

// TestRDSNetworkIsolation validates that the network architecture provides proper isolation for RDS.
// This ensures:
// - Private route table has no route to internet gateway
// - Private subnets are associated with the private route table
func TestRDSNetworkIsolation(t *testing.T) {
	t.Parallel()

	terraformOptions := VPCTestOptions(t)

	planStruct := terraform.InitAndPlanAndShowWithStruct(t, terraformOptions)
	require.NotNil(t, planStruct.RawPlan.PlannedValues)

	var (
		privateRouteTableFound       bool
		privateRouteTableHasIGWRoute bool
		routeTableAssociationCount   int
	)

	for _, resource := range planStruct.RawPlan.PlannedValues.RootModule.Resources {
		switch resource.Type {
		case "aws_route_table":
			if resource.Name == "private" {
				privateRouteTableFound = true
				values := resource.AttributeValues

				// Check for routes to internet gateway
				routes, ok := values["route"].([]interface{})
				if ok {
					for _, route := range routes {
						routeMap, ok := route.(map[string]interface{})
						if ok {
							// Check if route goes to internet gateway
							if _, hasGateway := routeMap["gateway_id"]; hasGateway {
								cidr, hasCIDR := routeMap["cidr_block"].(string)
								if hasCIDR && cidr == "0.0.0.0/0" {
									privateRouteTableHasIGWRoute = true
								}
							}
						}
					}
				}
			}

		case "aws_route_table_association":
			if resource.Name == "private" {
				routeTableAssociationCount++
			}
		}
	}

	assert.True(t, privateRouteTableFound, "Private route table should be defined")
	assert.False(t, privateRouteTableHasIGWRoute,
		"Private route table should NOT have a route to internet gateway")
	assert.GreaterOrEqual(t, routeTableAssociationCount, 2,
		"Private subnets should be associated with private route table")
}
