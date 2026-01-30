package broker

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"time"

	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/service/sqs"
	"github.com/aws/aws-sdk-go-v2/service/sqs/types"
	"github.com/google/uuid"
	"trip-service/internal/domain"
)

// TripEventManager handles business logic triggered by SQS events.
// This interface decouples the broker from the service implementation.
type TripEventManager interface {
	AssignDriver(ctx context.Context, tripID uuid.UUID, driverID uuid.UUID) error
	CompleteTrip(ctx context.Context, tripID uuid.UUID) error
}

// SQSMessageEnvelope represents the standard message structure used across services.
type SQSMessageEnvelope struct {
	EventType     string          `json:"eventType"`
	CorrelationID string          `json:"correlationId"`
	Payload       json.RawMessage `json:"payload"`
}

// TripCompletedPayload matches the "trip.completed" schema from documentation.
type TripCompletedPayload struct {
	TripID string `json:"tripId"`
	Status string `json:"status"`
}

// SQSConsumer manages polling from AWS SQS for trip-related events.
type SQSConsumer struct {
	client   *sqs.Client
	queueURL string
	svc      TripEventManager
}

// NewSQSConsumer creates a new consumer instance with modern endpoint resolution.
func NewSQSConsumer(cfg aws.Config, queueURL string, svc TripEventManager, brokerCfg *Config) *SQSConsumer {
	client := sqs.NewFromConfig(cfg, func(o *sqs.Options) {
		if brokerCfg.SQSEndpoint != "" {
			o.BaseEndpoint = aws.String(brokerCfg.SQSEndpoint)
		}
	})

	return &SQSConsumer{
		client:   client,
		queueURL: queueURL,
		svc:      svc,
	}
}

// Start begins the polling loop.
func (c *SQSConsumer) Start(ctx context.Context) error {
	if c.queueURL == "" {
		return fmt.Errorf("fatal error: SQS Queue URL is not set; consumer cannot start")
	}

	log.Printf("INFO: Starting SQS Consumer on queue: %s", c.queueURL)

	for {
		select {
		case <-ctx.Done():
			log.Println("INFO: Stopping SQS Consumer...")
			return nil
		default:
			c.poll(ctx)
		}
	}
}

func (c *SQSConsumer) poll(ctx context.Context) {
	output, err := c.client.ReceiveMessage(ctx, &sqs.ReceiveMessageInput{
		QueueUrl:            aws.String(c.queueURL),
		MaxNumberOfMessages: 10,
		WaitTimeSeconds:     20, // Long polling
		VisibilityTimeout:   30,
		AttributeNames:      []types.QueueAttributeName{types.QueueAttributeNameAll},
	})

	if err != nil {
		if errors.Is(err, context.Canceled) {
			return
		}
		log.Printf("ERROR: Failed to poll SQS: %v", err)
		time.Sleep(5 * time.Second) // Error backoff
		return
	}

	for _, msg := range output.Messages {
		msgID := aws.ToString(msg.MessageId)
		if err := c.processMessage(ctx, msg); err != nil {
			log.Printf("WARN: Failed to process message %s (will retry): %v", msgID, err)
		} else {
			c.deleteMessage(ctx, msg)
		}
	}
}

// processMessage unmarshals the envelope and routes to specific handlers based on EventType.
func (c *SQSConsumer) processMessage(ctx context.Context, msg types.Message) error {
	body := aws.ToString(msg.Body)
	msgID := aws.ToString(msg.MessageId)

	if body == "" {
		log.Printf("ERROR: Message %s received with empty body", msgID)
		return nil
	}

	var envelope SQSMessageEnvelope
	if err := json.Unmarshal([]byte(body), &envelope); err != nil {
		log.Printf("ERROR: Malformed JSON envelope in message %s: %v", msgID, err)
		return nil
	}

	// Route logic based on EventType
	switch envelope.EventType {
	case "driver.assigned":
		return c.handleDriverAssigned(ctx, envelope.Payload, msgID)
	case "trip.completed":
		return c.handleTripCompleted(ctx, envelope.Payload, msgID)
	default:
		log.Printf("INFO: Skipping message %s with unknown EventType: %s", msgID, envelope.EventType)
		return nil
	}
}

func (c *SQSConsumer) handleDriverAssigned(ctx context.Context, payload json.RawMessage, msgID string) error {
	var data struct {
		TripID   string `json:"tripId"`
		DriverID string `json:"driverId"`
	}

	if err := json.Unmarshal(payload, &data); err != nil {
		log.Printf("ERROR: Malformed driver.assigned payload in %s: %v", msgID, err)
		return nil
	}

	tripID, err := uuid.Parse(data.TripID)
	if err != nil {
		log.Printf("ERROR: Invalid Trip UUID in %s: %v", msgID, err)
		return nil
	}

	driverID, err := uuid.Parse(data.DriverID)
	if err != nil {
		log.Printf("ERROR: Invalid Driver UUID in %s: %v", msgID, err)
		return nil
	}

	err = c.svc.AssignDriver(ctx, tripID, driverID)
	if err != nil {
		if errors.Is(err, domain.ErrInvalidTripStatus) || errors.Is(err, domain.ErrTripNotFound) {
			log.Printf("INFO: Idempotency check for assignment %s: %v. Deleting.", msgID, err)
			return nil
		}
		return err
	}

	log.Printf("SUCCESS: Trip %s updated to ACTIVE with Driver %s", tripID, driverID)
	return nil
}

func (c *SQSConsumer) handleTripCompleted(ctx context.Context, payload json.RawMessage, msgID string) error {
	var data TripCompletedPayload
	if err := json.Unmarshal(payload, &data); err != nil {
		log.Printf("ERROR: Malformed trip.completed payload in %s: %v", msgID, err)
		return nil
	}

	tripID, err := uuid.Parse(data.TripID)
	if err != nil {
		log.Printf("ERROR: Invalid Trip UUID in completion event %s: %v", msgID, err)
		return nil
	}

	err = c.svc.CompleteTrip(ctx, tripID)
	if err != nil {
		if errors.Is(err, domain.ErrTripNotFound) {
			log.Printf("INFO: Trip %s not found for completion %s. Deleting.", tripID, msgID)
			return nil
		}
		return err
	}

	log.Printf("SUCCESS: Trip %s marked as COMPLETED via SQS", tripID)
	return nil
}

func (c *SQSConsumer) deleteMessage(ctx context.Context, msg types.Message) {
	if msg.ReceiptHandle == nil {
		return
	}

	_, err := c.client.DeleteMessage(ctx, &sqs.DeleteMessageInput{
		QueueUrl:      aws.String(c.queueURL),
		ReceiptHandle: msg.ReceiptHandle,
	})

	if err != nil {
		log.Printf("ERROR: Failed to delete message %s: %v", aws.ToString(msg.MessageId), err)
	}
}
