# Build stage
FROM golang:1.25.5-alpine AS builder
WORKDIR /app

# Optimize caching by copying dependency files first
COPY go.mod go.sum ./
RUN go mod download

# Copy source code and build the application
COPY . .
RUN go build -o /app/trip-service ./cmd/server/main.go

# Final stage
FROM alpine:3.21
# Install curl for healthchecks
RUN apk add --no-cache curl

WORKDIR /app

# Copy the binary and migrations first (as requested by mentor)
COPY --from=builder /app/trip-service .
COPY --from=builder /app/db/migrations ./migrations

# Create non-root user after COPY to follow mentor's instructions
# Note: This layer's cache will be invalidated whenever the binary changes
RUN addgroup -S appgroup && \
    adduser -S appuser -G appgroup && \
    chown -R appuser:appgroup /app

# Switch to the non-root user for runtime security
USER appuser

# Document the service port
EXPOSE 8081

# Native Docker healthcheck linked to the Go Chi router health endpoint
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8081/health || exit 1

# Start the application
CMD ["./trip-service"]
