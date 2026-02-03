# Trip Service API Documentation (Swagger/OpenAPI)

This document describes how to access and use the Swagger/OpenAPI documentation for the Trip Service REST API.

## Overview

Trip Service exposes a comprehensive OpenAPI 2.0 specification that documents all available endpoints, request/response schemas, validation rules, and error responses.

## Accessing Swagger UI

### Local Development

1. **Enable Swagger UI** by setting the environment variable:
   ```bash
   export ENABLE_SWAGGER=true
   ```

2. **Start the Trip Service**:
   ```bash
   go run cmd/server/main.go
   ```

3. **Access Swagger UI**:
   - URL: http://localhost:8081/swagger/
   - The interactive UI allows you to:
     - Browse all available endpoints
     - View request/response schemas
     - Test API calls directly from the browser
     - See validation rules and error responses

4. **Access OpenAPI JSON**:
   - URL: http://localhost:8081/openapi.json
   - Raw OpenAPI specification in JSON format
   - Can be imported into tools like Postman, Insomnia, or API testing frameworks

### Docker Compose

When running with docker-compose, add the environment variable to the service:

```yaml
trip-service:
  environment:
    - ENABLE_SWAGGER=true
  ports:
    - "8081:8081"
```

Then access at: http://localhost:8081/swagger/

### AWS Development Environment

#### Option 1: Via Load Balancer (Recommended)

If Trip Service is behind an Application Load Balancer:

1. Ensure `ENABLE_SWAGGER=true` is set in the ECS task definition or EC2 environment
2. Access via the load balancer URL:
   ```
   https://<alb-dns-name>/swagger/
   ```

#### Option 2: Via EC2 Instance (Direct Access)

If Trip Service runs on EC2:

1. **SSH into the EC2 instance** (bastion host):
   ```bash
   ssh -i ~/.ssh/key.pem ec2-user@<bastion-ip>
   ssh <trip-service-private-ip>
   ```

2. **Port forward to local machine**:
   ```bash
   ssh -i ~/.ssh/key.pem -L 8081:localhost:8081 ec2-user@<ec2-ip>
   ```

3. **Access locally**:
   ```
   http://localhost:8081/swagger/
   ```

#### Option 3: Via Session Manager (SSM)

If SSM is enabled:

```bash
aws ssm start-session --target <instance-id> \
  --document-name AWS-StartPortForwardingSession \
  --parameters '{"portNumber":["8081"],"localPortNumber":["8081"]}'
```

Then access at: http://localhost:8081/swagger/

## Security Considerations

**IMPORTANT**: Swagger UI is designed for development and testing only.

- **Production**: Swagger UI should be **DISABLED** (`ENABLE_SWAGGER=false` or unset)
- **Staging/Dev**: Swagger UI can be enabled for testing
- **API Keys**: If your API requires authentication, configure it in the OpenAPI spec

Current security setup:
- Swagger UI is **conditionally enabled** via environment variable
- No authentication is required (add if needed for your use case)

## Available Endpoints

The following endpoints are documented in the OpenAPI spec:

| Method | Endpoint                     | Description                      |
|--------|------------------------------|----------------------------------|
| GET    | `/health`                    | Service health check             |
| POST   | `/trips`                     | Create a new trip                |
| GET    | `/trips/{id}`                | Get trip by ID                   |
| PATCH  | `/trips/{id}/assign-driver`  | Assign driver to existing trip   |

## Regenerating Documentation

If you modify API handlers or add new endpoints, regenerate the OpenAPI spec:

```bash
# Install swag if not already installed
go install github.com/swaggo/swag/cmd/swag@latest

# Generate docs
swag init -g cmd/server/main.go -o docs

# Verify generation
ls -lh docs/
```

Files generated:
- `docs/docs.go` - Go package with embedded spec
- `docs/swagger.json` - OpenAPI spec in JSON format
- `docs/swagger.yaml` - OpenAPI spec in YAML format

**IMPORTANT**: Always commit the generated files to git so they're available in Docker containers.

## CI/CD Integration

The CI pipeline automatically:

1. Validates that `swagger.json` is syntactically correct
2. Checks that all required endpoints are documented
3. Verifies the committed spec matches the code
4. Fails the build if docs are out of sync

If CI fails with "swagger.json differs from committed version":
```bash
swag init -g cmd/server/main.go -o docs
git add docs/
git commit -m "Update OpenAPI spec"
```

## Testing with Swagger UI

### Example: Create a Trip

1. Navigate to http://localhost:8081/swagger/
2. Find the `POST /trips` endpoint
3. Click "Try it out"
4. Enter the request body:
   ```json
   {
     "passenger_id": "123e4567-e89b-12d3-a456-426614174000",
     "pickup": "123 Main St, City",
     "dropoff": "456 Oak Ave, City"
   }
   ```
5. Click "Execute"
6. View the response with the created trip including generated ID

### Example: Assign Driver

1. Find the `PATCH /trips/{id}/assign-driver` endpoint
2. Enter the trip ID from the previous step
3. Enter the request body:
   ```json
   {
     "driver_id": "223e4567-e89b-12d3-a456-426614174001"
   }
   ```
4. Click "Execute"
5. Verify the driver assignment response

## Troubleshooting

### Swagger UI returns 404

- Ensure `ENABLE_SWAGGER=true` is set
- Check service logs for "Swagger UI enabled" message
- Verify you're accessing `/swagger/` (with trailing slash)

### OpenAPI spec is outdated

- Regenerate with: `swag init -g cmd/server/main.go -o docs`
- Restart the service
- Hard refresh the browser (Ctrl+Shift+R or Cmd+Shift+R)

### Cannot access in AWS

- Verify security groups allow traffic on port 8081
- Check that `ENABLE_SWAGGER=true` in ECS task definition or EC2 environment
- Use SSM Session Manager for secure access without exposing ports

## Additional Resources

- [Swag Documentation](https://github.com/swaggo/swag)
- [OpenAPI 2.0 Specification](https://swagger.io/specification/v2/)
- [Swagger UI GitHub](https://github.com/swagger-api/swagger-ui)
