package broker

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"sync"
	"time"

	amqp "github.com/rabbitmq/amqp091-go"
	"trip-service/internal/domain" // Corrected: removed drive-ops/ prefix
)

// Publisher defines the interface for publishing events
type Publisher interface {
	PublishTripCreated(ctx context.Context, event *domain.TripCreatedEvent) error
	Close() error
}

// RabbitMQPublisher implements Publisher for RabbitMQ
type RabbitMQPublisher struct {
	mu           sync.Mutex
	conn         *amqp.Connection
	channel      *amqp.Channel
	exchangeName string
}

// NewRabbitMQPublisher creates a new RabbitMQ publisher
func NewRabbitMQPublisher(config *Config) (*RabbitMQPublisher, error) {
	conn, err := amqp.Dial(config.URL)
	if err != nil {
		return nil, fmt.Errorf("failed to connect to RabbitMQ: %w", err)
	}

	channel, err := conn.Channel()
	if err != nil {
		if closeErr := conn.Close(); closeErr != nil {
			log.Printf("Error closing connection after channel failure: %v", closeErr)
		}
		return nil, fmt.Errorf("failed to open channel: %w", err)
	}

	// [FIXED] Uses config.ExchangeType which was restored in config.go
	err = channel.ExchangeDeclare(
		config.ExchangeName, // name
		config.ExchangeType, // type
		true,                // durable
		false,               // auto-deleted
		false,               // internal
		false,               // no-wait
		nil,                 // arguments
	)
	if err != nil {
		// Clean up on failure
		_ = channel.Close()
		_ = conn.Close()
		return nil, fmt.Errorf("failed to declare exchange: %w", err)
	}

	log.Printf("INFO: Connected to RabbitMQ, exchange: %s", config.ExchangeName)

	return &RabbitMQPublisher{
		conn:         conn,
		channel:      channel,
		exchangeName: config.ExchangeName,
	}, nil
}

// PublishTripCreated publishes a trip.event.created event
func (p *RabbitMQPublisher) PublishTripCreated(ctx context.Context, event *domain.TripCreatedEvent) error {
	body, err := json.Marshal(event)
	if err != nil {
		return fmt.Errorf("failed to marshal event: %w", err)
	}

	// [CRITICAL] Mutex Lock: amqp.Channel is NOT thread-safe for publishing
	p.mu.Lock()
	defer p.mu.Unlock()

	err = p.channel.PublishWithContext(
		ctx,
		p.exchangeName,      // exchange
		"trip.event.created", // routing key
		false,               // mandatory
		false,               // immediate
		amqp.Publishing{
			ContentType:  "application/json",
			Body:         body,
			DeliveryMode: amqp.Persistent,
			Timestamp:    time.Now(),
		},
	)

	if err != nil {
		return fmt.Errorf("failed to publish RabbitMQ event: %w", err)
	}

	log.Printf("INFO: Published RabbitMQ event: type=%s, trip_id=%s", event.EventType, event.Payload.TripID)
	return nil
}

// Close closes the RabbitMQ connection
func (p *RabbitMQPublisher) Close() error {
	p.mu.Lock()
	defer p.mu.Unlock()

	var chanErr, connErr error

	if p.channel != nil {
		chanErr = p.channel.Close()
	}

	if p.conn != nil {
		connErr = p.conn.Close()
	}

	log.Println("INFO: Closed RabbitMQ connection")

	if chanErr != nil {
		return chanErr
	}
	return connErr
}
