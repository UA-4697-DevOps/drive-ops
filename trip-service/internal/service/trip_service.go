package service

import (
	"context"
	"errors"
	"fmt"
	"log"

	"trip-service/internal/broker"
	"trip-service/internal/domain"
	"trip-service/internal/repository"

	"github.com/google/uuid"
)

// EventPublisher defines the behavior required for outgoing events.
// This decouples the service from specific implementations like RabbitMQ or SQS.
type EventPublisher interface {
	PublishTripCreated(ctx context.Context, event *domain.TripCreatedEvent) error
}

// TripServiceInterface defines the behavior of the trip service
type TripServiceInterface interface {
	CreateTrip(ctx context.Context, trip *domain.Trip) error
	GetTrip(ctx context.Context, id uuid.UUID) (*domain.Trip, error)
	AssignDriver(ctx context.Context, tripID uuid.UUID, driverID uuid.UUID) error
	CompleteTrip(ctx context.Context, tripID uuid.UUID) error
	CheckHealth(ctx context.Context) error
}

type TripService struct {
	repo      *repository.TripRepository
	publisher EventPublisher // Changed from broker.Publisher
}

// NewTripService creates a new instance of TripService.
func NewTripService(repo *repository.TripRepository, publisher EventPublisher) *TripService {
	if repo == nil {
		panic("repository cannot be nil")
	}
	if publisher == nil {
		panic("publisher cannot be nil")
	}
	return &TripService{
		repo:      repo,
		publisher: publisher,
	}
}

// CreateTrip initiates a new trip request
func (s *TripService) CreateTrip(ctx context.Context, trip *domain.Trip) error {
	if trip.Pickup == "" || trip.Dropoff == "" || trip.PassengerID == uuid.Nil {
		return domain.ErrInvalidCreateTripData
	}

	trip.ID = uuid.New()
	trip.Status = domain.TripStatusPending

	var event *domain.TripCreatedEvent

	// Wrap "insert trip + publish event" in a single DB transaction.
	if err := s.repo.WithTransaction(ctx, func(txRepo *repository.TripRepository) error {
		// 1. Persist to Database
		if err := txRepo.Create(ctx, trip); err != nil {
			return err
		}

		// 2. Notify Driver Service via SQS
		event = broker.BuildTripCreatedEvent(trip, trip.ID.String())

		// Use the generic publisher interface
		if err := s.publisher.PublishTripCreated(ctx, event); err != nil {
			log.Printf("ERROR: Failed to publish trip.created for trip_id=%s correlation_id=%s: %v", trip.ID, event.CorrelationID, err)
			return fmt.Errorf("failed to notify drivers via SQS: %w", err)
		}

		log.Printf("INFO: Successfully published trip.created for trip_id=%s correlation_id=%s", trip.ID, event.CorrelationID)
		return nil
	}); err != nil {
		return err
	}

	return nil
}

// GetTrip retrieves a trip by its unique identifier
func (s *TripService) GetTrip(ctx context.Context, id uuid.UUID) (*domain.Trip, error) {
	return s.repo.GetByID(ctx, id)
}

// AssignDriver handles the business logic for assigning a driver
func (s *TripService) AssignDriver(ctx context.Context, tripID uuid.UUID, driverID uuid.UUID) error {
	if tripID == uuid.Nil || driverID == uuid.Nil {
		return domain.ErrInvalidID
	}

	return s.repo.AssignDriver(ctx, tripID, driverID)
}

// CompleteTrip marks a trip as finished using an atomic database update.
func (s *TripService) CompleteTrip(ctx context.Context, tripID uuid.UUID) error {
	if tripID == uuid.Nil {
		return domain.ErrInvalidID
	}

	if err := s.repo.CompleteTrip(ctx, tripID); err != nil {
		if errors.Is(err, domain.ErrInvalidTripStatus) {
			log.Printf("INFO: Trip %s skip completion (already done).", tripID)
			return nil
		}
		return err
	}

	log.Printf("SUCCESS: Trip %s marked as COMPLETED", tripID)
	return nil
}

// CheckHealth verifies the database connection status.
func (s *TripService) CheckHealth(ctx context.Context) error {
	return s.repo.Ping(ctx)
}
