# Build stage
FROM golang:1.25.5-alpine AS builder
WORKDIR /app
COPY . .
RUN go build -o trip-service ./cmd/server/main.go

# Final stage
FROM alpine:3.21
# Add non-root user for security
RUN addgroup -S appgroup && adduser -S appuser -G appgroup
WORKDIR /app

# Copy binary and migrations
COPY --from=builder /app/trip-service .
COPY --from=builder /app/db/migrations ./migrations

# Set permissions and switch user
RUN chown -R appuser:appgroup /app
USER appuser

CMD ["./trip-service"]