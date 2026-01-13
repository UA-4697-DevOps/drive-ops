package broker

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"sync"

	"trip-service/internal/domain"

	"github.com/google/uuid"
	amqp "github.com/rabbitmq/amqp091-go"
)

// TripAssigner defines the capability required by the consumer
type TripAssigner interface {
	AssignDriver(ctx context.Context, tripID uuid.UUID, driverID uuid.UUID) error
}

// Consumer defines the interface for consuming events
type Consumer interface {
	Start(ctx context.Context) error
	Close() error
}

// RabbitMQConsumer implements Consumer for RabbitMQ
type RabbitMQConsumer struct {
	conn         *amqp.Connection
	channel      *amqp.Channel
	service      TripAssigner
	exchangeName string
	queueName    string
	wg           sync.WaitGroup
}

// NewRabbitMQConsumer creates a new RabbitMQ consumer
func NewRabbitMQConsumer(config *Config, svc TripAssigner) (*RabbitMQConsumer, error) {
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

	cleanup := func() {
		if channel != nil {
			if err := channel.Close(); err != nil {
				log.Printf("Error closing channel during cleanup: %v", err)
			}
		}
		if err := conn.Close(); err != nil {
			log.Printf("Error closing connection during cleanup: %v", err)
		}
	}
	// Declare exchange to ensure it exists
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
		cleanup()
		return nil, fmt.Errorf("failed to declare exchange: %w", err)
	}
	// Declare a queue
	q, err := channel.QueueDeclare(
		"trip_service_consumer", // name
		true,                    // durable
		false,                   // delete when unused
		false,                   // exclusive
		false,                   // no-wait
		nil,                     // arguments
	)
	if err != nil {
		cleanup()
		return nil, fmt.Errorf("failed to declare queue: %w", err)
	}
	// Bind queue to exchange
	err = channel.QueueBind(
		q.Name,                       // queue name
		"trip.event.driver_assigned", // routing key
		config.ExchangeName,          // exchange
		false,
		nil,
	)
	if err != nil {
		cleanup()
		return nil, fmt.Errorf("failed to bind queue: %w", err)
	}

	return &RabbitMQConsumer{
		conn:         conn,
		channel:      channel,
		service:      svc,
		exchangeName: config.ExchangeName,
		queueName:    q.Name,
	}, nil
}

// Start begins consuming messages
func (c *RabbitMQConsumer) Start(ctx context.Context) error {
	msgs, err := c.channel.Consume(
		c.queueName, // queue
		"",          // consumer
		false,       // auto-ack
		false,       // exclusive
		false,       // no-local
		false,       // no-wait
		nil,         // args
	)
	if err != nil {
		return fmt.Errorf("failed to register consumer: %w", err)
	}

	c.wg.Add(1)
	go func() {
		defer c.wg.Done()
		log.Println("Started consuming events...")
		for {
			select {
			case <-ctx.Done():
				log.Println("Consumer stopping...")
				return
			case d, ok := <-msgs:
				if !ok {
					log.Println("RabbitMQ channel closed")
					return
				}
				c.handleDelivery(ctx, d)
			}
		}
	}()

	return nil
}

// handleDelivery processes a single message
func (c *RabbitMQConsumer) handleDelivery(ctx context.Context, d amqp.Delivery) {
	// Acknowledge message always to prevent loops, unless we want to requeue on transient failures
	// For MVP: Log and Drop strategies.
	defer func() {
		if err := d.Ack(false); err != nil {
			log.Printf("Error acknowledging message: %v", err)
		}
	}()

	if d.RoutingKey == "trip.event.driver_assigned" {
		if err := c.handleDriverAssigned(ctx, d.Body); err != nil {
			log.Printf("Error handling driver assigned event: %v", err)
			return
		}
	}
}

func (c *RabbitMQConsumer) handleDriverAssigned(ctx context.Context, body []byte) error {
	var event domain.DriverAssignedEvent
	if err := json.Unmarshal(body, &event); err != nil {
		return fmt.Errorf("failed to unmarshal JSON: %w", err)
	}

	// Validate IDs
	tripID, err := uuid.Parse(event.Payload.TripID)
	if err != nil {
		return fmt.Errorf("invalid trip ID '%s': %w", event.Payload.TripID, err)
	}

	driverID, err := uuid.Parse(event.Payload.DriverID)
	if err != nil {
		return fmt.Errorf("invalid driver ID '%s': %w", event.Payload.DriverID, err)
	}

	log.Printf("Processing driver assignment: trip=%s, driver=%s", tripID, driverID)

	// Delegate to service
	if err := c.service.AssignDriver(ctx, tripID, driverID); err != nil {
		return fmt.Errorf("failed to assign driver via service: %w", err)
	}

	log.Printf("Successfully processed driver assignment for trip %s", tripID)
	return nil
}

// Close gracefully shuts down the consumer
func (c *RabbitMQConsumer) Close() error {
	var errs []error
	
	// Wait for processing to finish if we were using a more complex shutdown
	// For now, channel close is enough
	
	if err := c.channel.Close(); err != nil {
		errs = append(errs, err)
	}
	if err := c.conn.Close(); err != nil {
		errs = append(errs, err)
	}
	
	// Wait for goroutine
	c.wg.Wait()

	if len(errs) > 0 {
		return fmt.Errorf("errors closing consumer: %v", errs)
	}
	return nil
}
