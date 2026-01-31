package broker

import (
	"errors"
	"log"
	"os"
)

// Config holds Broker (Legacy RabbitMQ & Modern SQS) configuration
type Config struct {
	// RabbitMQ (Legacy)
	URL          string
	ExchangeName string
	ExchangeType string // [RESTORED] Prevent build errors in legacy files

	// SQS FIFO Queue URLs (Production)
	SQS_TRIP_CREATED_URL    string
	SQS_DRIVER_ASSIGNED_URL string
	SQS_TRIP_COMPLETED_URL  string

	AWSRegion string
}

// LoadConfig loads broker configuration from environment variables
func LoadConfig() (*Config, error) {
	// 1. SQS Configuration (Primary for Phase 2)
	sqsCreatedURL := os.Getenv("SQS_TRIP_CREATED_URL")
	sqsAssignedURL := os.Getenv("SQS_DRIVER_ASSIGNED_URL")
	sqsCompletedURL := os.Getenv("SQS_TRIP_COMPLETED_URL")
	awsRegion := getEnv("AWS_REGION", "us-east-2")

	// Strict Validation: Fail fast if SQS URLs are missing in Production
	if sqsCreatedURL == "" || sqsAssignedURL == "" || sqsCompletedURL == "" {
		return nil, errors.New("missing required SQS Queue URLs; check SQS_TRIP_CREATED_URL, SQS_DRIVER_ASSIGNED_URL, and SQS_TRIP_COMPLETED_URL")
	}

	// 2. RabbitMQ Configuration (Kept for Bridge Stability)
	rabbitmqURL := os.Getenv("RABBITMQ_URL")
	if rabbitmqURL == "" {
		log.Println("INFO: RABBITMQ_URL not set; legacy bridge functions will be disabled")
	}

	return &Config{
		URL:                     rabbitmqURL,
		ExchangeName:            getEnv("RABBITMQ_EXCHANGE", "trip_events"),
		ExchangeType:            getEnv("RABBITMQ_EXCHANGE_TYPE", "topic"), // [RESTORED]
		SQS_TRIP_CREATED_URL:    sqsCreatedURL,
		SQS_DRIVER_ASSIGNED_URL: sqsAssignedURL,
		SQS_TRIP_COMPLETED_URL:  sqsCompletedURL,
		AWSRegion:               awsRegion,
	}, nil
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}
