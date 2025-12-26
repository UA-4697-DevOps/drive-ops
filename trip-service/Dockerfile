# Build stage
FROM golang:1.24.0-alpine AS builder
WORKDIR /app
COPY . .
RUN go build -o trip-service ./cmd/main.go

# Final stage
FROM alpine:3.18
# Add non-root user for security
RUN addgroup -S appgroup && adduser -S appuser -G appgroup
WORKDIR /app

# Copy binary (migrations handled by trip-migrations service)
COPY --from=builder /app/trip-service .

# Set permissions and switch user
RUN chown -R appuser:appgroup /app
USER appuser

CMD ["./trip-service"]