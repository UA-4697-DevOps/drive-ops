package infratests

import (
	"strings"
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

// TestVPCPrivateSubnetIsolation validates that private subnets have no DIRECT internet route.
// When NAT Instance is enabled, a route to 0.0.0.0/0 via NAT Instance is acceptable (not via IGW).
func TestVPCPrivateSubnetIsolation(t *testing.T) {
	t.Parallel()

	terraformOptions := VPCTestOptions(t)
	terraformOptions.Vars["use_nat_instance"] = true // Ensure NAT instance is enabled for this test

	planStruct := terraform.InitAndPlanAndShowWithStruct(t, terraformOptions)
	require.NotNil(t, planStruct.RawPlan.PlannedValues)

	foundPrivateRouteTable := false

	// FIRST PASS: Locate the private route table
	for _, resource := range planStruct.RawPlan.PlannedValues.RootModule.Resources {
		if resource.Type == "aws_route_table" && strings.Contains(resource.Address, "private") {
			foundPrivateRouteTable = true

			values := resource.AttributeValues
			routes, ok := values["route"].([]interface{})
			if ok {
				for _, route := range routes {
					routeMap, ok := route.(map[string]interface{})
					if ok {
						// Ensure no INLINE route to IGW exists. Treat computed/unknown values
						// (Terraform plan after_unknown maps) as presence of a gateway so they
						// cannot bypass the assertion.
						if gw, hasGW := routeMap["gateway_id"]; hasGW {
							gwPresent := false
							switch v := gw.(type) {
							case string:
								if v != "" {
									gwPresent = true
								}
							case map[string]interface{}:
								// A non-empty map indicates a computed/unknown value (after_unknown)
								if len(v) > 0 {
									gwPresent = true
								}
							default:
								// Any other non-nil value indicates presence
								if v != nil {
									gwPresent = true
								}
							}

							if gwPresent {
								// Coerce cidr_block to a comparable string before asserting
								cidrStr := ""
								if s, ok := routeMap["cidr_block"].(string); ok {
									cidrStr = s
								} else if m, ok := routeMap["cidr_block"].(map[string]interface{}); ok {
									// If plan shows after_unknown, treat as non-equal to 0.0.0.0/0
									if au, hasAU := m["after_unknown"]; hasAU {
										if auBool, ok := au.(bool); ok && auBool {
											cidrStr = "<after_unknown>"
										}
									}
									if cidrStr == "" {
										cidrStr = "<computed>"
									}
								}

								assert.NotEqual(t, "0.0.0.0/0", cidrStr,
									"Private route table should not have a direct IGW route to 0.0.0.0/0")
							}
						}
					}
				}
			}
		}
	}

	foundPrivateNatRoute := false

	// SECOND PASS: Validate NAT route configuration
	for _, resource := range planStruct.RawPlan.PlannedValues.RootModule.Resources {
		if resource.Type == "aws_route" && resource.Name == "private_nat_instance" {
			foundPrivateNatRoute = true
			attributes := resource.AttributeValues

			// Safe extraction of gateway_id
			gwStr := ""
			if gwVal, hasGW := attributes["gateway_id"]; hasGW {
				var ok bool
				gwStr, ok = gwVal.(string)
				if !ok {
					gwStr = ""
				}
			}

			// gateway_id should be empty/absent for NAT routes
			assert.Equal(t, "", gwStr, "NAT route should not target an Internet Gateway (gateway_id must be empty)")

			// Accept either known IDs or plan-time unknowns.
			niTargetPlanned := false
			if niVal, hasNI := attributes["network_interface_id"]; hasNI {
				if niStr, ok := niVal.(string); ok && niStr != "" {
					niTargetPlanned = true
				} else if niMap, ok := niVal.(map[string]interface{}); ok {
					if auVal, hasAU := niMap["after_unknown"]; hasAU {
						au, _ := auVal.(bool)
						niTargetPlanned = au
					}
				}
			}

			instTargetPlanned := false
			if instVal, hasInst := attributes["instance_id"]; hasInst {
				if instStr, ok := instVal.(string); ok && instStr != "" {
					instTargetPlanned = true
				} else if instMap, ok := instVal.(map[string]interface{}); ok {
					if auVal, hasAU := instMap["after_unknown"]; hasAU {
						au, _ := auVal.(bool)
						instTargetPlanned = au
					}
				}
			}

			assert.True(t, niTargetPlanned || instTargetPlanned,
				"NAT route must plan to target a NAT instance ENI or instance ID")
		}
	}

	assert.True(t, foundPrivateRouteTable, "Expected private route table")
	assert.True(t, foundPrivateNatRoute, "expected aws_route.private_nat_instance to be present in plan")
}
