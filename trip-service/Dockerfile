FROM golang:1.25-alpine AS builder

WORKDIR /app

COPY go.mod go.sum ./
RUN go mod download

COPY . .

RUN go build -o /app/trip-service cmd/server/main.go

FROM alpine:latest

RUN apk add --no-cache curl

WORKDIR /root/

COPY --from=builder /app/trip-service .

EXPOSE 8081

CMD ["./trip-service"]
