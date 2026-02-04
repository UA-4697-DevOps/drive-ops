# Terratest Infrastructure Tests

This directory contains Go-based infrastructure tests using [Terratest](https://terratest.gruntwork.io/) to validate Terraform/Terragrunt modules.

## Prerequisites

- **Go** 1.25+ installed
- **Terraform** 1.10+ installed
- **AWS credentials** configured (for tests that interact with AWS)

## Running Tests Locally

### Quick Start

```bash
# Navigate to the terratest directory
cd infra/terratest

# Download dependencies
go mod download

# Run all tests (plan-only, no AWS resources created)
go test -v ./...

# Run specific test file
go test -v -run TestVPC ./...
go test -v -run TestSQS ./...
go test -v -run TestRDS ./...
```

### Test Categories

| Test File | What It Validates |
|-----------|-------------------|
| `vpc_test.go` | VPC outputs, security group rules, subnet CIDR allocation, private subnet isolation |
| `sqs_test.go` | SQS queue configuration, FIFO settings, DLQ wiring, IAM policies |
| `rds_test.go` | RDS security group rules, private subnet placement, network isolation |

### Plan-Only Tests

All tests use `terraform plan` to validate configurations **without creating real AWS resources**. This makes them:

- ✅ **Safe** - No infrastructure changes
- ✅ **Fast** - No waiting for resource creation
- ✅ **Free** - No AWS costs

### Running with Real AWS Resources

> ⚠️ **Warning**: The following will create real AWS resources and incur costs.

For integration testing with real infrastructure:

```bash
# Set your AWS credentials
export AWS_ACCESS_KEY_ID=your-key
export AWS_SECRET_ACCESS_KEY=your-secret
export AWS_DEFAULT_REGION=eu-central-1

# Run with a specific timeout
go test -v -timeout 30m ./...
```

## Writing New Tests

### Test Structure

```go
func TestMyModule(t *testing.T) {
    t.Parallel()

    modulePath := GetModulePath(t, "my-module")
    terraformOptions := DefaultTerraformOptions(t, modulePath, map[string]interface{}{
        "my_var": "value",
    })

    // Plan only - no resources created
    planStruct := terraform.InitAndPlanAndShowWithStruct(t, terraformOptions)

    // Assert on plan outputs
    assert.NotNil(t, planStruct.RawPlan.PlannedValues)
}
```

### Best Practices

1. **Use `t.Parallel()`** for faster test execution
2. **Use plan-only tests** when possible to avoid costs
3. **Use helper functions** from `test_helper.go` for consistency
4. **Test outputs and configurations**, not just resource existence

## CI Integration

Terratest is **not** run in CI due to cost and security considerations. Instead, CI performs:

- `terraform fmt -check -recursive`
- `terraform validate` on each module
- `terragrunt hclfmt --terragrunt-check`

See `.github/workflows/infra-ci.yml` for details.
