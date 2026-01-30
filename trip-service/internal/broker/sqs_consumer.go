package broker

import (
	"context"
	"encoding/json"
	"errors"
	"log"
	"time"

	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/service/sqs"
	"github.com/aws/aws-sdk-go-v2/service/sqs/types"
	"github.com/google/uuid"
	"trip-service/internal/domain"
)

// DriverAssigner interface decouples the broker from the service implementation
type DriverAssigner interface {
	AssignDriver(ctx context.Context, tripID uuid.UUID, driverID uuid.UUID) error
}

// SQSConsumer manages polling from AWS SQS
type SQSConsumer struct {
	client   *sqs.Client
	queueURL string
	svc      DriverAssigner
}

// NewSQSConsumer creates a new consumer instance with modern endpoint resolution
func NewSQSConsumer(cfg aws.Config, queueURL string, svc DriverAssigner, brokerCfg *Config) *SQSConsumer {
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

// Start begins the polling loop
func (c *SQSConsumer) Start(ctx context.Context) error {
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
		// [FIXED] Safe MessageId extraction for logging
		msgID := aws.ToString(msg.MessageId)
		if err := c.processMessage(ctx, msg); err != nil {
			log.Printf("WARN: Failed to process message %s (will retry): %v", msgID, err)
		} else {
			c.deleteMessage(ctx, msg)
		}
	}
}

func (c *SQSConsumer) processMessage(ctx context.Context, msg types.Message) error {
	// [FIXED] Extract values safely using aws.ToString to prevent nil pointer panics
	body := aws.ToString(msg.Body)
	msgID := aws.ToString(msg.MessageId)

	if body == "" {
		log.Printf("ERROR: Message %s received with empty body", msgID)
		return nil // Nothing to process, delete it
	}

	var event DriverAssignedEvent
	if err := json.Unmarshal([]byte(body), &event); err != nil {
		log.Printf("ERROR: Malformed JSON in message %s: %v", msgID, err)
		return nil // Invalid JSON, delete it
	}

	log.Printf("INFO: Received driver.assigned event: TripID=%s DriverID=%s", 
		event.Payload.TripID, event.Payload.DriverID)

	tripID, err := uuid.Parse(event.Payload.TripID)
	if err != nil {
		log.Printf("ERROR: Invalid Trip UUID in message %s: %v", msgID, err)
		return nil
	}
	driverID, err := uuid.Parse(event.Payload.DriverID)
	if err != nil {
		log.Printf("ERROR: Invalid Driver UUID in message %s: %v", msgID, err)
		return nil
	}

	// Call the service method
	err = c.svc.AssignDriver(ctx, tripID, driverID)
	if err != nil {
		if errors.Is(err, domain.ErrInvalidTripStatus) || errors.Is(err, domain.ErrTripNotFound) {
			log.Printf("INFO: Idempotency check for message %s: %v. Deleting.", msgID, err)
			return nil
		}
		return err // Retry on other errors
	}

	log.Printf("SUCCESS: Trip %s updated to ACTIVE with Driver %s", tripID, driverID)
	return nil
}

func (c *SQSConsumer) deleteMessage(ctx context.Context, msg types.Message) {
	msgID := aws.ToString(msg.MessageId)

	// [FIXED] Explicit nil check for ReceiptHandle as it is a required pointer for DeleteMessage
	if msg.ReceiptHandle == nil {
		log.Printf("ERROR: Cannot delete message %s: ReceiptHandle is nil", msgID)
		return
	}

	_, err := c.client.DeleteMessage(ctx, &sqs.DeleteMessageInput{
		QueueUrl:      aws.String(c.queueURL),
		ReceiptHandle: msg.ReceiptHandle,
	})

	if err != nil {
		log.Printf("ERROR: Failed to delete message %s: %v", msgID, err)
	} else {
		log.Printf("DEBUG: SQS Message %s successfully deleted", msgID)
	}
}
