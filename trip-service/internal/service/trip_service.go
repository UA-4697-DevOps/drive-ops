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
	"gorm.io/gorm"
)

var (
	ErrTripNotFound = errors.New("trip not found")
	ErrInvalidInput = errors.New("pickup and dropoff locations are required")
)

// TripServiceInterface описує поведінку сервісу
type TripServiceInterface interface {
	CreateTrip(ctx context.Context, trip *domain.Trip) error
	GetTrip(ctx context.Context, id uuid.UUID) (*domain.Trip, error)
	CheckHealth(ctx context.Context) error
}

type TripService struct {
	repo      *repository.TripRepository
	publisher broker.Publisher
}

func NewTripService(repo *repository.TripRepository, publisher broker.Publisher) *TripService {
	return &TripService{
		repo:      repo,
		publisher: publisher,
	}
}

func (s *TripService) CreateTrip(ctx context.Context, trip *domain.Trip) error {
	if trip.Pickup == "" || trip.Dropoff == "" {
		return ErrInvalidInput
	}
	if trip.PassengerID == uuid.Nil {
		return errors.New("passenger_id is required")
	}

	trip.ID = uuid.New()
	trip.Status = domain.TripStatusPending

	// Create trip in database
	if err := s.repo.Create(ctx, trip); err != nil {
		return err
	}

	// Publish trip.event.created event
	// Note: We don't fail the trip creation if event publishing fails.
	// This follows eventual consistency pattern - trip is created successfully,
	// and we log the publish failure for monitoring/retry.
	event := broker.BuildTripCreatedEvent(trip, trip.ID.String())
	if err := s.publisher.PublishTripCreated(ctx, event); err != nil {
		log.Printf("ERROR: Failed to publish trip.event.created for trip_id=%s: %v", trip.ID, err)
		// TODO: Consider implementing outbox pattern or retry mechanism for failed publishes
	} else {
		log.Printf("Successfully published trip.event.created for trip_id=%s", trip.ID)
	}

	return nil
}

func (s *TripService) GetTrip(ctx context.Context, id uuid.UUID) (*domain.Trip, error) {
	trip, err := s.repo.GetByID(ctx, id)
	if err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			return nil, ErrTripNotFound
		}
		return nil, fmt.Errorf("failed to get trip: %w", err)
	}
	return trip, nil
}

func (s *TripService) CheckHealth(ctx context.Context) error {
	sqlDB, err := s.repo.DB().DB()
	if err != nil {
		return fmt.Errorf("failed to get database connection: %w", err)
	}

	if err := sqlDB.PingContext(ctx); err != nil {
		return fmt.Errorf("database health check failed: %w", err)
	}

	return nil
}
