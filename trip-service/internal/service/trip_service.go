package service

import (
	"context"
	"fmt"
	"log"

	"trip-service/internal/broker"
	"trip-service/internal/domain"
	"trip-service/internal/repository"

	"github.com/google/uuid"
)

// TripServiceInterface defines the behavior of the trip service
type TripServiceInterface interface {
	CreateTrip(ctx context.Context, trip *domain.Trip) error
	GetTrip(ctx context.Context, id uuid.UUID) (*domain.Trip, error)
	AssignDriver(ctx context.Context, tripID uuid.UUID, driverID uuid.UUID) error
	CheckHealth(ctx context.Context) error
}

type TripService struct {
	repo      *repository.TripRepository
	publisher broker.Publisher
}

// NewTripService creates a new instance of TripService with RabbitMQ publisher.
func NewTripService(repo *repository.TripRepository, publisher broker.Publisher) *TripService {
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

// CreateTrip handles the logic for initiating a new trip request (Phase 1)
func (s *TripService) CreateTrip(ctx context.Context, trip *domain.Trip) error {
	if trip.Pickup == "" || trip.Dropoff == "" || trip.PassengerID == uuid.Nil {
		return domain.ErrInvalidCreateTripData
	}

	trip.ID = uuid.New()
	trip.Status = domain.TripStatusPending

	if err := s.repo.Create(ctx, trip); err != nil {
		return err
	}

	// Phase 2: Notify other services about new trip
	event := broker.BuildTripCreatedEvent(trip, trip.ID.String())
	if err := s.publisher.PublishTripCreated(ctx, event); err != nil {
		log.Printf("ERROR: Failed to publish trip.event.created for trip_id=%s: %v", trip.ID, err)
	} else {
		log.Printf("Successfully published trip.event.created for trip_id=%s", trip.ID)
	}

	return nil
}

// GetTrip retrieves a trip by its unique identifier (Phase 4)
func (s *TripService) GetTrip(ctx context.Context, id uuid.UUID) (*domain.Trip, error) {
	trip, err := s.repo.GetByID(ctx, id)
	if err != nil {
		return nil, err
	}
	return trip, nil
}

// AssignDriver handles the business logic for assigning a driver (Phase 3)
func (s *TripService) AssignDriver(ctx context.Context, tripID uuid.UUID, driverID uuid.UUID) error {
	if tripID == uuid.Nil || driverID == uuid.Nil {
		return domain.ErrInvalidID
	}

	return s.repo.AssignDriver(ctx, tripID, driverID)
}

// CheckHealth verifies the database connection status.
// FIX: Now uses the encapsulated Ping() method from the repository.
func (s *TripService) CheckHealth(ctx context.Context) error {
	if err := s.repo.Ping(ctx); err != nil {
		return fmt.Errorf("database health check failed: %w", err)
	}
	return nil
}
