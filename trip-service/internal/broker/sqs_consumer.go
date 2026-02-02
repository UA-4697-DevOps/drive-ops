package broker

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"log"
	"time"

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

type TripCompletedPayload struct {
	TripID string `json:"tripId"`
	Status string `json:"status"`
}

// SQSConsumer manages polling from AWS SQS for trip-related events.
type SQSConsumer struct {
	client   *sqs.Client
	queueURL string
	svc      TripEventManager
	isMock   bool
}

func NewSQSConsumer(cfg aws.Config, queueURL string, svc TripEventManager) *SQSConsumer {
	// Detect mock mode from environment
    if os.Getenv("AWS_ACCESS_KEY_ID") == "mock" {
        log.Printf("CI DEBUG: SQS Consumer initializing in MOCK MODE for queue: %s", queueURL)
        return &SQSConsumer{
            client:   nil,
            queueURL: queueURL,
            svc:      svc,
            isMock:   true,
        }
    }

	client := sqs.NewFromConfig(cfg)
	return &SQSConsumer{
		client:   client,
		queueURL: queueURL,
		svc:      svc,
	}
}

func (c *SQSConsumer) Start(ctx context.Context) error {
	if c.queueURL == "" {
		return fmt.Errorf("fatal error: SQS Queue URL is not set; consumer cannot start")
	}
	// [FIXED] Bypass polling if in mock mode to keep CI logs clean
    if c.isMock {
        log.Printf("CI DEBUG: SQS Consumer (MOCK) is running but will not poll SQS.")
        <-ctx.Done() // Wait for shutdown signal without polling
        return nil
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
		WaitTimeSeconds:     20,
		VisibilityTimeout:   30,
		AttributeNames:      []types.QueueAttributeName{types.QueueAttributeNameAll},
	})

	if err != nil {
		if errors.Is(err, context.Canceled) {
			return
		}
		log.Printf("ERROR: Failed to poll SQS: %v", err)
		time.Sleep(5 * time.Second)
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
	var envelope SQSMessageEnvelope
	if err := json.Unmarshal([]byte(body), &envelope); err != nil {
		log.Printf("ERROR: Malformed JSON envelope: %v. Deleting message.", err)
		return nil // Return nil to delete poison pill
	}

	switch envelope.EventType {
	case "driver.assigned":
		return c.handleDriverAssigned(ctx, envelope.Payload, *msg.MessageId)
	case "trip.completed":
		return c.handleTripCompleted(ctx, envelope.Payload, *msg.MessageId)
	default:
		log.Printf("INFO: Skipping unknown event type: %s", envelope.EventType)
		return nil
	}
}

// [FIXED] Added missing handler for driver assignment
func (c *SQSConsumer) handleDriverAssigned(ctx context.Context, payload json.RawMessage, msgID string) error {
	var data struct {
		TripID   string `json:"tripId"`
		DriverID string `json:"driverId"`
	}
	if err := json.Unmarshal(payload, &data); err != nil {
		log.Printf("ERROR: Malformed driver.assigned payload: %v", err)
		return nil // Delete malformed message
	}

	tripID, errT := uuid.Parse(data.TripID)
	driverID, errD := uuid.Parse(data.DriverID)
	if errT != nil || errD != nil {
		log.Printf("ERROR: Invalid UUIDs in assignment message %s", msgID)
		return nil 
	}

	return c.svc.AssignDriver(ctx, tripID, driverID)
}

// [FIXED] Added missing handler for trip completion
func (c *SQSConsumer) handleTripCompleted(ctx context.Context, payload json.RawMessage, msgID string) error {
	var data TripCompletedPayload
	if err := json.Unmarshal(payload, &data); err != nil {
		log.Printf("ERROR: Malformed trip.completed payload: %v", err)
		return nil
	}

	tripID, err := uuid.Parse(data.TripID)
	if err != nil {
		log.Printf("ERROR: Invalid TripID in completion message %s", msgID)
		return nil
	}

	return c.svc.CompleteTrip(ctx, tripID)
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
