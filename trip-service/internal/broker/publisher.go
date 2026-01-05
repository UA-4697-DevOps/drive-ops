package broker

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"time"

	amqp "github.com/rabbitmq/amqp091-go"
	"trip-service/internal/domain"
)

// Publisher defines the interface for publishing events
type Publisher interface {
	PublishTripCreated(ctx context.Context, event *domain.TripCreatedEvent) error
	Close() error
}

// RabbitMQPublisher implements Publisher for RabbitMQ
type RabbitMQPublisher struct {
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

	// Declare exchange
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
		if closeErr := channel.Close(); closeErr != nil {
			log.Printf("Error closing channel after exchange declare failure: %v", closeErr)
		}
		if closeErr := conn.Close(); closeErr != nil {
			log.Printf("Error closing connection after exchange declare failure: %v", closeErr)
		}
		return nil, fmt.Errorf("failed to declare exchange: %w", err)
	}

	log.Printf("Connected to RabbitMQ, exchange: %s", config.ExchangeName)

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
		return fmt.Errorf("failed to publish event: %w", err)
	}

	log.Printf("Published event: type=%s, trip_id=%s", event.EventType, event.Payload.TripID)
	return nil
}

// Close closes the RabbitMQ connection
func (p *RabbitMQPublisher) Close() error {
	if p.channel != nil {
		if err := p.channel.Close(); err != nil {
			log.Printf("Error closing channel: %v", err)
		}
	}
	if p.conn != nil {
		if err := p.conn.Close(); err != nil {
			log.Printf("Error closing connection: %v", err)
			return err
		}
	}
	log.Println("Closed RabbitMQ connection")
	return nil
}
