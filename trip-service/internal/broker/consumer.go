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
	// Bind queue to exchange for driver_assigned events
	err = channel.QueueBind(
		q.Name,                       // queue name
		"trip.event.driver_assigned", // routing key
		config.ExchangeName,          // exchange
		false,
		nil,
	)
	if err != nil {
		cleanup()
		return nil, fmt.Errorf("failed to bind queue to driver_assigned: %w", err)
	}

	// Bind queue to exchange for completed events
	err = channel.QueueBind(
		q.Name,                  // queue name
		"trip.event.completed",  // routing key
		config.ExchangeName,     // exchange
		false,
		nil,
	)
	if err != nil {
		cleanup()
		return nil, fmt.Errorf("failed to bind queue to completed: %w", err)
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
		c.queueName, // queue
		"",          // consumer
		false,       // auto-ack (we manual ack in handleDelivery)
		false,       // exclusive
		false,       // no-local
		false,       // no-wait
		nil,         // args
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

// handleDelivery processes a single message
func (c *RabbitMQConsumer) handleDelivery(ctx context.Context, d amqp.Delivery) {
	// Acknowledge message to prevent it from getting stuck in "Unacked" state
	defer func() {
		if err := d.Ack(false); err != nil {
			log.Printf("ERROR: Error acknowledging message: %v", err)
		}
	}()

	// Note: Routing keys here use the legacy "trip.event.*" format
	switch d.RoutingKey {
	case "trip.event.driver_assigned":
		if err := c.handleDriverAssigned(ctx, d.Body); err != nil {
			log.Printf("ERROR: Error handling driver assigned event: %v", err)
		}
	case "trip.event.completed":
		if err := c.handleTripCompleted(ctx, d.Body); err != nil {
			log.Printf("ERROR: Error handling trip completed event: %v", err)
		}
	default:
		log.Printf("INFO: Received message with unknown routing key: %s", d.RoutingKey)
	}
}

func (c *RabbitMQConsumer) handleDriverAssigned(ctx context.Context, body []byte) error {
	var event domain.DriverAssignedEvent
	if err := json.Unmarshal(body, &event); err != nil {
		return fmt.Errorf("failed to unmarshal JSON: %w", err)
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

	if err := c.service.AssignDriver(ctx, tripID, driverID); err != nil {
		return fmt.Errorf("failed to assign driver via service: %w", err)
	}

	return nil
}

func (c *RabbitMQConsumer) handleTripCompleted(ctx context.Context, body []byte) error {
	var event domain.TripCompletedEvent
	if err := json.Unmarshal(body, &event); err != nil {
		return fmt.Errorf("failed to unmarshal JSON: %w", err)
	}

	tripID, err := uuid.Parse(event.Payload.TripID)
	if err != nil {
		return fmt.Errorf("invalid trip ID '%s': %w", event.Payload.TripID, err)
	}

	log.Printf("INFO: Processing trip completion (RabbitMQ): trip=%s", tripID)

	if err := c.service.CompleteTrip(ctx, tripID); err != nil {
		return fmt.Errorf("failed to complete trip via service: %w", err)
	}

	return nil
}

// Close gracefully shuts down the RabbitMQ connection
func (c *RabbitMQConsumer) Close() error {
	var errs []error
	
	if err := c.channel.Close(); err != nil {
		errs = append(errs, err)
	}
	if err := c.conn.Close(); err != nil {
		errs = append(errs, err)
	}
	
	c.wg.Wait()

	if len(errs) > 0 {
		return fmt.Errorf("errors closing RabbitMQ consumer: %v", errs)
	}
	return nil
}
