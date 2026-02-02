package broker

import (
	"errors"
	"os"
)

// Config holds Broker (Modern SQS FIFO) configuration
type Config struct {
	// SQS FIFO Queue URLs (Production)
	SQS_TRIP_CREATED_URL    string
	SQS_DRIVER_ASSIGNED_URL string
	SQS_TRIP_COMPLETED_URL  string

	AWSRegion string
}

// LoadConfig loads broker configuration from environment variables
func LoadConfig() (*Config, error) {
	// 1. SQS Configuration (Unified Cloud-Native Path)
	sqsCreatedURL := os.Getenv("SQS_TRIP_CREATED_URL")
	sqsAssignedURL := os.Getenv("SQS_DRIVER_ASSIGNED_URL")
	sqsCompletedURL := os.Getenv("SQS_TRIP_COMPLETED_URL")
	awsRegion := getEnv("AWS_REGION", "us-east-2")

	// Strict Validation: Fail fast if SQS URLs are missing in Production
	if sqsCreatedURL == "" || sqsAssignedURL == "" || sqsCompletedURL == "" {
		return nil, errors.New("missing required SQS Queue URLs; check SQS_TRIP_CREATED_URL, SQS_DRIVER_ASSIGNED_URL, and SQS_TRIP_COMPLETED_URL")
	}

	return &Config{
		SQS_TRIP_CREATED_URL:    sqsCreatedURL,
		SQS_DRIVER_ASSIGNED_URL: sqsAssignedURL,
		SQS_TRIP_COMPLETED_URL:  sqsCompletedURL,
		AWSRegion:               awsRegion,
	}, nil
}

// getEnv is a helper to provide default values for non-critical environment variables
func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}
