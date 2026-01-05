package broker

import (
	"fmt"
	"net/url"
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

		// Reject insecure default credentials
		if username == "guest" && password == "guest" {
			return nil, fmt.Errorf("invalid RABBITMQ_URL: default guest/guest credentials are not allowed for security reasons")
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
			return nil, fmt.Errorf("RABBITMQ_USER environment variable is required")
		}
		if password == "" {
			return nil, fmt.Errorf("RABBITMQ_PASSWORD environment variable is required")
		}

		connURL = fmt.Sprintf("amqp://%s:%s@%s:%s/", user, password, host, port)
	}

	exchangeName := getEnv("RABBITMQ_EXCHANGE", "trip_events")
	exchangeType := getEnv("RABBITMQ_EXCHANGE_TYPE", "topic")

	return &Config{
		URL:          connURL,
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
