package broker

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"time"

	"trip-service/internal/domain"

	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/service/sqs"
	"github.com/aws/aws-sdk-go-v2/service/sqs/types"
	"github.com/google/uuid"
)

// TripEventManager handles business logic triggered by SQS events.
type TripEventManager interface {
	AssignDriver(ctx context.Context, tripID uuid.UUID, driverID uuid.UUID) error
	CompleteTrip(ctx context.Context, tripID uuid.UUID) error
}

// SQSMessageEnvelope represents the standard message structure used across services.
type SQSMessageEnvelope struct {
	Version       string          `json:"version"`
	MessageID     string          `json:"messageId"`
	Timestamp     string          `json:"timestamp"`
	CorrelationID string          `json:"correlationId"`
	EventType     string          `json:"eventType"`
	Source        string          `json:"source"`
	Payload       json.RawMessage `json:"payload"`
}

// --- PUBLISHER LOGIC ---

// SQSPublisher handles sending events to SQS FIFO queues.
type SQSPublisher struct {
	client   *sqs.Client
	queueURL string
}

// NewSQSPublisher creates a new instance of SQSPublisher.
// Simplified: Removed BaseEndpoint override to use standard AWS SQS URLs.
func NewSQSPublisher(cfg aws.Config, queueURL string) *SQSPublisher {
	client := sqs.NewFromConfig(cfg)
	return &SQSPublisher{
		client:   client,
		queueURL: queueURL,
	}
}

// Close satisfies the broker.Publisher interface. 
// SQS uses internal connection pooling and does not require manual closing like RabbitMQ.
func (p *SQSPublisher) Close() error {
	log.Println("INFO: SQS Publisher closing (no-op)")
	return nil
}

// PublishTripCreated sends the "trip.created" event to SQS FIFO queue.
// [FIXED] Updated signature to match the Publisher interface in publisher.go
func (p *SQSPublisher) PublishTripCreated(ctx context.Context, event *domain.TripCreatedEvent) error {
	body, err := json.Marshal(event)
	if err != nil {
		return fmt.Errorf("failed to marshal trip created event: %w", err)
	}

	// FIFO requirements: MessageGroupId and unique DeduplicationId.
	// We use the trip ID to ensure per-trip ordering as per design decisions.
	msgGroupID := fmt.Sprintf("trip-%s", event.Payload.TripID)
	dedupID := uuid.New().String()

	_, err = p.client.SendMessage(ctx, &sqs.SendMessageInput{
		QueueUrl:               aws.String(p.queueURL),
		MessageBody:            aws.String(string(body)),
		MessageGroupId:         aws.String(msgGroupID),
		MessageDeduplicationId: aws.String(dedupID),
	})

	if err != nil {
		return fmt.Errorf("failed to send trip.created to SQS: %w", err)
	}

	log.Printf("INFO: Published trip.created to SQS: trip_id=%s", event.Payload.TripID)
	return nil
}

// --- CONSUMER LOGIC ---

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
// NewSQSConsumer creates a new consumer instance.
// Simplified: Removed BaseEndpoint override to use standard AWS SQS URLs.
func NewSQSConsumer(cfg aws.Config, queueURL string, svc TripEventManager) *SQSConsumer {
	client := sqs.NewFromConfig(cfg)

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
		if err := c.processMessage(ctx, msg); err != nil {
			log.Printf("WARN: Failed to process message %s: %v", *msg.MessageId, err)
		} else {
			c.deleteMessage(ctx, msg)
		}
	}
}

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
		return nil
	}

	driverID, err := uuid.Parse(data.DriverID)
	if err != nil {
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
		return nil
	}

	tripID, err := uuid.Parse(data.TripID)
	if err != nil {
		return nil
	}

	err = c.svc.CompleteTrip(ctx, tripID)
	if err != nil {
		if errors.Is(err, domain.ErrTripNotFound) || errors.Is(err, domain.ErrInvalidTripStatus) {
			log.Printf("INFO: Trip %s skip completion (not found or invalid status) in message %s. Deleting.", tripID, msgID)
			return nil
		}
		return err
	}

	log.Printf("SUCCESS: Trip %s marked as COMPLETED via SQS", tripID)
	return nil
}

func (c *SQSConsumer) deleteMessage(ctx context.Context, msg types.Message) {
	_, err := c.client.DeleteMessage(ctx, &sqs.DeleteMessageInput{
		QueueUrl:      aws.String(c.queueURL),
		ReceiptHandle: msg.ReceiptHandle,
	})
	if err != nil {
		log.Printf("ERROR: Failed to delete message %s from SQS: %v", *msg.MessageId, err)
	}
}
