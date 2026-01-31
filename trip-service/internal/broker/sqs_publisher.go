package broker

import (
	"context"
	"encoding/json"
	"fmt"
	"log"

	"trip-service/internal/domain" // Corrected path

	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/service/sqs"
)

// SQSPublisher handles sending events to SQS FIFO queues.
type SQSPublisher struct {
	client   *sqs.Client
	queueURL string
}

func NewSQSPublisher(cfg aws.Config, queueURL string) *SQSPublisher {
	client := sqs.NewFromConfig(cfg)
	return &SQSPublisher{
		client:   client,
		queueURL: queueURL,
	}
}

// PublishTripCreated sends the "trip.created" event to SQS FIFO queue.
func (p *SQSPublisher) PublishTripCreated(ctx context.Context, event *domain.TripCreatedEvent) error {
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
