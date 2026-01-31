package broker

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"sync"

	"trip-service/internal/domain" // Corrected: removed drive-ops/ prefix

	"github.com/google/uuid"
	amqp "github.com/rabbitmq/amqp091-go"
)

// TripAssigner defines the capability required by the consumer
type TripAssigner interface {
	AssignDriver(ctx context.Context, tripID uuid.UUID, driverID uuid.UUID) error
	CompleteTrip(ctx context.Context, tripID uuid.UUID) error
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
		_ = conn.Close()
		return nil, fmt.Errorf("failed to open channel: %w", err)
	}

	// [REFINED] Setting QOS to 1 ensures the consumer only gets one message at a time.
	// This is critical when using Nack with Requeue to prevent overwhelming the service.
	err = channel.Qos(1, 0, false)
	if err != nil {
		_ = channel.Close()
		_ = conn.Close()
		return nil, fmt.Errorf("failed to set QOS: %w", err)
	}

	cleanup := func() {
		_ = channel.Close()
		_ = conn.Close()
	}

	// Declare exchange
	err = channel.ExchangeDeclare(
		config.ExchangeName,
		config.ExchangeType,
		true,  // durable
		false, // auto-deleted
		false, // internal
		false, // no-wait
		nil,   // arguments
	)
	if err != nil {
		cleanup()
		return nil, fmt.Errorf("failed to declare exchange: %w", err)
	}

	// Declare queue
	q, err := channel.QueueDeclare(
		"trip_service_consumer",
		true,  // durable
		false, // delete when unused
		false, // exclusive
		false, // no-wait
		nil,   // arguments
	)
	if err != nil {
		cleanup()
		return nil, fmt.Errorf("failed to declare queue: %w", err)
	}

	// Binding logic for driver_assigned and completed events...
	routingKeys := []string{"trip.event.driver_assigned", "trip.event.completed"}
	for _, key := range routingKeys {
		err = channel.QueueBind(q.Name, key, config.ExchangeName, false, nil)
		if err != nil {
			cleanup()
			return nil, fmt.Errorf("failed to bind queue to %s: %w", key, err)
		}
	}

	return &RabbitMQConsumer{
		conn:         conn,
		channel:      channel,
		service:      svc,
		exchangeName: config.ExchangeName,
		queueName:    q.Name,
	}, nil
}

// Start begins consuming messages from RabbitMQ
func (c *RabbitMQConsumer) Start(ctx context.Context) error {
	msgs, err := c.channel.Consume(
		c.queueName,
		"",
		false, // auto-ack is FALSE (Manual Ack required)
		false,
		false,
		false,
		nil,
	)
	if err != nil {
		return fmt.Errorf("failed to register RabbitMQ consumer: %w", err)
	}

	c.wg.Add(1)
	go func() {
		defer c.wg.Done()
		log.Println("INFO: Started consuming RabbitMQ events...")
		for {
			select {
			case <-ctx.Done():
				log.Println("INFO: RabbitMQ Consumer stopping...")
				return
			case d, ok := <-msgs:
				if !ok {
					log.Println("WARN: RabbitMQ channel closed")
					return
				}
				c.handleDelivery(ctx, d)
			}
		}
	}()

	return nil
}

// handleDelivery processes a single message with reliable Ack/Nack strategy
func (c *RabbitMQConsumer) handleDelivery(ctx context.Context, d amqp.Delivery) {
	var err error

	// 1. Route message based on legacy keys
	switch d.RoutingKey {
	case "trip.event.driver_assigned":
		err = c.handleDriverAssigned(ctx, d.Body)
	case "trip.event.completed":
		err = c.handleTripCompleted(ctx, d.Body)
	default:
		log.Printf("INFO: Unknown routing key: %s. Acknowledging and dropping.", d.RoutingKey)
		_ = d.Ack(false)
		return
	}

	// 2. Handle Outcome
	if err != nil {
		log.Printf("ERROR: Processing failed for %s: %v", d.RoutingKey, err)
		
		// [RELIABILITY FIX] Nack with requeue=true
		// If DB is down, the message stays in the queue to try again later.
		if nackErr := d.Nack(false, true); nackErr != nil {
			log.Printf("CRITICAL: Failed to nack message: %v", nackErr)
		}
		return
	}

	// 3. Success Path: Manual Acknowledge
	if ackErr := d.Ack(false); ackErr != nil {
		log.Printf("ERROR: Failed to acknowledge message: %v", ackErr)
	}
}

func (c *RabbitMQConsumer) handleDriverAssigned(ctx context.Context, body []byte) error {
	var event domain.DriverAssignedEvent
	if err := json.Unmarshal(body, &event); err != nil {
		return fmt.Errorf("unmarshal JSON: %w", err)
	}

	tripID, err := uuid.Parse(event.Payload.TripID)
	if err != nil {
		return fmt.Errorf("invalid trip ID '%s': %w", event.Payload.TripID, err)
	}

	driverID, err := uuid.Parse(event.Payload.DriverID)
	if err != nil {
		return fmt.Errorf("invalid driver ID '%s': %w", event.Payload.DriverID, err)
	}

	log.Printf("INFO: Processing driver assignment (RabbitMQ): trip=%s, driver=%s", tripID, driverID)
	return c.service.AssignDriver(ctx, tripID, driverID)
}

func (c *RabbitMQConsumer) handleTripCompleted(ctx context.Context, body []byte) error {
	var event domain.TripCompletedEvent
	if err := json.Unmarshal(body, &event); err != nil {
		return fmt.Errorf("unmarshal JSON: %w", err)
	}

	tripID, err := uuid.Parse(event.Payload.TripID)
	if err != nil {
		return fmt.Errorf("invalid trip ID '%s': %w", event.Payload.TripID, err)
	}

	log.Printf("INFO: Processing trip completion (RabbitMQ): trip=%s", tripID)
	return c.service.CompleteTrip(ctx, tripID)
}

// Close gracefully shuts down the RabbitMQ connection
func (c *RabbitMQConsumer) Close() error {
	if c.channel != nil {
		_ = c.channel.Close()
	}
	if c.conn != nil {
		_ = c.conn.Close()
	}
	c.wg.Wait()
	return nil
}
