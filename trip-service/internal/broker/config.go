package broker

import (
	"fmt"
	"os"
)

// Config holds RabbitMQ connection configuration
type Config struct {
	URL          string
	ExchangeName string
	ExchangeType string
}

// LoadConfig loads broker configuration from environment variables
func LoadConfig() (*Config, error) {
	// Support both RABBITMQ_URL (Docker/single string) and individual env vars (local dev)
	var url string
	if rabbitmqURL := os.Getenv("RABBITMQ_URL"); rabbitmqURL != "" {
		url = rabbitmqURL
	} else {
		// Build URL from individual components
		host := getEnv("RABBITMQ_HOST", "localhost")
		port := getEnv("RABBITMQ_PORT", "5672")
		user := os.Getenv("RABBITMQ_USER")
		password := os.Getenv("RABBITMQ_PASSWORD")

		// Validate required credentials
		if user == "" {
			return nil, fmt.Errorf("RABBITMQ_USER environment variable is required")
		}
		if password == "" {
			return nil, fmt.Errorf("RABBITMQ_PASSWORD environment variable is required")
		}

		url = fmt.Sprintf("amqp://%s:%s@%s:%s/", user, password, host, port)
	}

	exchangeName := getEnv("RABBITMQ_EXCHANGE", "trip_events")
	exchangeType := getEnv("RABBITMQ_EXCHANGE_TYPE", "topic")

	return &Config{
		URL:          url,
		ExchangeName: exchangeName,
		ExchangeType: exchangeType,
	}, nil
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}
