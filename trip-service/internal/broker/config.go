package broker

import (
	"fmt"
	"log"
	"net/url"
	"os"
)

// Config holds Broker (RabbitMQ & SQS) connection configuration
type Config struct {
	URL          string
	ExchangeName string
	ExchangeType string

	// SQS functional queue URLs
	SQS_TRIP_CREATED_URL    string // [NEW] Added for Phase 2: Trip Creation
	SQS_DRIVER_ASSIGNED_URL string
	SQS_TRIP_COMPLETED_URL  string 
	
	AWSRegion   string
	SQSEndpoint string // LocalStack override
}

// LoadConfig loads broker configuration from environment variables
func LoadConfig() (*Config, error) {
	// 1. Legacy RabbitMQ Configuration (Kept for bridge stability)
	var connURL string
	if rabbitmqURL := os.Getenv("RABBITMQ_URL"); rabbitmqURL != "" {
		connURL = rabbitmqURL
	} else {
		host := getEnv("RABBITMQ_HOST", "localhost")
		port := getEnv("RABBITMQ_PORT", "5672")
		user := os.Getenv("RABBITMQ_USER")
		password := os.Getenv("RABBITMQ_PASSWORD")

		if user == "" || password == "" {
			log.Println("Warning: RabbitMQ credentials not set; ignore if running SQS-only mode")
		}

		encodedUser := url.QueryEscape(user)
		encodedPassword := url.QueryEscape(password)
		connURL = fmt.Sprintf("amqp://%s:%s@%s:%s/", encodedUser, encodedPassword, host, port)
	}

	exchangeName := getEnv("RABBITMQ_EXCHANGE", "trip_events")
	exchangeType := getEnv("RABBITMQ_EXCHANGE_TYPE", "topic")

	// 2. SQS Configuration [UPDATED]
	// Retrieve all functional FIFO queue URLs from environment
	sqsCreatedURL := os.Getenv("SQS_TRIP_CREATED_URL")    // [NEW]
	sqsAssignedURL := os.Getenv("SQS_DRIVER_ASSIGNED_URL")
	sqsCompletedURL := os.Getenv("SQS_TRIP_COMPLETED_URL")
	
	awsRegion := getEnv("AWS_REGION", "us-east-2") 
	sqsEndpoint := os.Getenv("SQS_ENDPOINT") 

	// Validation: Ensure the primary migration URL is present
	if sqsCreatedURL == "" {
		log.Println("Warning: SQS_TRIP_CREATED_URL is missing; publishing will fail")
	}

	return &Config{
		URL:                     connURL,
		ExchangeName:            exchangeName,
		ExchangeType:            exchangeType,
		SQS_TRIP_CREATED_URL:    sqsCreatedURL,    // [NEW]
		SQS_DRIVER_ASSIGNED_URL: sqsAssignedURL,
		SQS_TRIP_COMPLETED_URL:  sqsCompletedURL, 
		AWSRegion:               awsRegion,
		SQSEndpoint:             sqsEndpoint,
	}, nil
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}
