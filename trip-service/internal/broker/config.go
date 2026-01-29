package broker

import (
	"fmt"
	"net/url"
	"os"
)

// Config holds Broker (RabbitMQ & SQS) connection configuration
type Config struct {
	URL          string
	ExchangeName string
	ExchangeType string

	// SQS specific
	SQSQueueURL string
	AWSRegion   string
}

// LoadConfig loads broker configuration from environment variables
func LoadConfig() (*Config, error) {
	// 1. RabbitMQ Configuration
	// Support both RABBITMQ_URL (Docker/single string) and individual env vars (local dev)
	var connURL string
	if rabbitmqURL := os.Getenv("RABBITMQ_URL"); rabbitmqURL != "" {
		// Validate RABBITMQ_URL
		parsedURL, err := url.Parse(rabbitmqURL)
		if err != nil {
			return nil, fmt.Errorf("invalid RABBITMQ_URL: failed to parse: %w", err)
		}

		// Check scheme
		if parsedURL.Scheme != "amqp" && parsedURL.Scheme != "amqps" {
			return nil, fmt.Errorf("invalid RABBITMQ_URL: scheme must be 'amqp' or 'amqps', got '%s'", parsedURL.Scheme)
		}

		// Check credentials are present
		if parsedURL.User == nil {
			return nil, fmt.Errorf("invalid RABBITMQ_URL: credentials are required")
		}

		username := parsedURL.User.Username()
		password, _ := parsedURL.User.Password()

		// Validate credentials are not empty
		if username == "" {
			return nil, fmt.Errorf("invalid RABBITMQ_URL: username cannot be empty")
		}
		if password == "" {
			return nil, fmt.Errorf("invalid RABBITMQ_URL: password cannot be empty")
		}

		connURL = rabbitmqURL
	} else {
		// Build URL from individual components
		host := getEnv("RABBITMQ_HOST", "localhost")
		port := getEnv("RABBITMQ_PORT", "5672")
		user := os.Getenv("RABBITMQ_USER")
		password := os.Getenv("RABBITMQ_PASSWORD")

		// Validate required credentials
		if user == "" {
			// Instead of failing, we can allow SQS-only mode if needed, 
			// but for now we keep existing logic and just add SQS
			log.Println("Warning: RABBITMQ_USER not set, RabbitMQ may fail to connect")
		}

		// URL-encode credentials to handle special characters
		encodedUser := url.QueryEscape(user)
		encodedPassword := url.QueryEscape(password)

		connURL = fmt.Sprintf("amqp://%s:%s@%s:%s/", encodedUser, encodedPassword, host, port)
	}

	exchangeName := getEnv("RABBITMQ_EXCHANGE", "trip_events")
	exchangeType := getEnv("RABBITMQ_EXCHANGE_TYPE", "topic")

	// 2. SQS Configuration
	sqsQueueURL := os.Getenv("SQS_QUEUE_URL")
	awsRegion := getEnv("AWS_REGION", "us-east-1")

	return &Config{
		URL:          connURL,
		ExchangeName: exchangeName,
		ExchangeType: exchangeType,
		SQSQueueURL:  sqsQueueURL,
		AWSRegion:    awsRegion,
	}, nil
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}
