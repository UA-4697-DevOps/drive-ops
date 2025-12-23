# Stage 1: Build
FROM golang:1.21-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN go build -o trip-service ./cmd/main.go

# Stage 2: Final image
FROM alpine:latest
WORKDIR /root/
COPY --from=builder /app/trip-service .
COPY --from=builder /app/db/migrations ./db/migrations

EXPOSE 8080
CMD ["./trip-service"]