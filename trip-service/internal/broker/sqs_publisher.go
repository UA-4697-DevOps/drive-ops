package broker

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"os"

	"trip-service/internal/domain" // Corrected path

	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/service/sqs"
)

// SQSPublisher handles sending events to SQS FIFO queues.
type SQSPublisher struct {
	client   *sqs.Client
	queueURL string
	isMock   bool // Flag to signal mock behavior
}

func NewSQSPublisher(cfg aws.Config, queueURL string) *SQSPublisher {
	// Detect mock mode from environment
    if os.Getenv("AWS_ACCESS_KEY_ID") == "mock" {
        log.Println("CI DEBUG: SQS Publisher starting in MOCK MODE (No real AWS calls)")
        return &SQSPublisher{
            client:   nil,
            queueURL: queueURL,
            isMock:   true,
        }
    }
	
	client := sqs.NewFromConfig(cfg)
	return &SQSPublisher{
		client:   client,
		queueURL: queueURL,
		isMock:   false,
	}
}

// PublishTripCreated sends the "trip.created" event to SQS FIFO queue.
func (p *SQSPublisher) PublishTripCreated(ctx context.Context, event *domain.TripCreatedEvent) error {
	// If in Mock Mode, log the event data instead of attempting a network call
    if p.isMock {
        log.Printf("MOCK PUBLISH: trip.created -> ID: %s | Group: trip-%s", 
            event.Payload.TripID, event.Payload.TripID)
        return nil
    }
	
	body, err := json.Marshal(event)
	if err != nil {
		return fmt.Errorf("failed to marshal event: %w", err)
	}

	// [FIXED] MessageGroupId: Stable grouping for FIFO ordering
	msgGroupID := fmt.Sprintf("trip-%s", event.Payload.TripID)

	// [FIXED] MessageDeduplicationId: Stable ID to prevent duplicate deliveries on retry
	dedupID := fmt.Sprintf("trip-created-%s", event.Payload.TripID)

	_, err = p.client.SendMessage(ctx, &sqs.SendMessageInput{
		QueueUrl:               aws.String(p.queueURL),
		MessageBody:            aws.String(string(body)),
		MessageGroupId:         aws.String(msgGroupID),
		MessageDeduplicationId: aws.String(dedupID),
	})

	if err != nil {
		return fmt.Errorf("failed to push to SQS: %w", err)
	}

	log.Printf("INFO: Published trip.created to SQS: trip_id=%s", event.Payload.TripID)
	return nil
}

func (p *SQSPublisher) Close() error {
	return nil
}
