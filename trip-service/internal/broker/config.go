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

	// SQS specific
	SQS_DRIVER_ASSIGNED_URL string
	SQS_TRIP_COMPLETED_URL  string // [ADD THIS] Required for Phase 3 completion
	AWSRegion               string
	SQSEndpoint             string // Needed for LocalStack overrides
}

// LoadConfig loads broker configuration from environment variables
func LoadConfig() (*Config, error) {
	// 1. RabbitMQ Configuration
	var connURL string
	if rabbitmqURL := os.Getenv("RABBITMQ_URL"); rabbitmqURL != "" {
		parsedURL, err := url.Parse(rabbitmqURL)
		if err != nil {
			return nil, fmt.Errorf("invalid RABBITMQ_URL: failed to parse: %w", err)
		}

		if parsedURL.Scheme != "amqp" && parsedURL.Scheme != "amqps" {
			return nil, fmt.Errorf("invalid RABBITMQ_URL: scheme must be 'amqp' or 'amqps', got '%s'", parsedURL.Scheme)
		}

		if parsedURL.User == nil {
			return nil, fmt.Errorf("invalid RABBITMQ_URL: credentials are required")
		}

		username := parsedURL.User.Username()
		password, _ := parsedURL.User.Password()

		if username == "" {
			return nil, fmt.Errorf("invalid RABBITMQ_URL: username cannot be empty")
		}
		if password == "" {
			return nil, fmt.Errorf("invalid RABBITMQ_URL: password cannot be empty")
		}

		connURL = rabbitmqURL
	} else {
		host := getEnv("RABBITMQ_HOST", "localhost")
		port := getEnv("RABBITMQ_PORT", "5672")
		user := os.Getenv("RABBITMQ_USER")
		password := os.Getenv("RABBITMQ_PASSWORD")

		// Warning only (allows running SQS-only mode)
		if user == "" || password == "" {
			log.Println("Warning: RabbitMQ credentials not fully set, connection might fail if required")
		}

		encodedUser := url.QueryEscape(user)
		encodedPassword := url.QueryEscape(password)
		connURL = fmt.Sprintf("amqp://%s:%s@%s:%s/", encodedUser, encodedPassword, host, port)
	}

	exchangeName := getEnv("RABBITMQ_EXCHANGE", "trip_events")
	exchangeType := getEnv("RABBITMQ_EXCHANGE_TYPE", "topic")

	// 2. SQS Configuration
	// Read explicit functional queue URLs from environment
	sqsAssignedURL := os.Getenv("SQS_DRIVER_ASSIGNED_URL")
	sqsCompletedURL := os.Getenv("SQS_TRIP_COMPLETED_URL")
	
	awsRegion := getEnv("AWS_REGION", "us-east-2") 
	sqsEndpoint := os.Getenv("SQS_ENDPOINT") 

	return &Config{
		URL:                     connURL,
		ExchangeName:            exchangeName,
		ExchangeType:            exchangeType,
		SQS_DRIVER_ASSIGNED_URL: sqsAssignedURL,
		SQS_TRIP_COMPLETED_URL:  sqsCompletedURL, // [ADD THIS] Mapping the environment variable
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
