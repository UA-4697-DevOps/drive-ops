package service

import (
	"context"
	"fmt"

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
	repo *repository.TripRepository
}

// NewTripService creates a new instance of TripService
func NewTripService(repo *repository.TripRepository) *TripService {
	return &TripService{repo: repo}
}

// CreateTrip handles the logic for initiating a new trip request
func (s *TripService) CreateTrip(ctx context.Context, trip *domain.Trip) error {
	// Validation check using domain errors for 400 Bad Request responses
	if trip.Pickup == "" || trip.Dropoff == "" || trip.PassengerID == uuid.Nil {
		return domain.ErrInvalidTripData
	}

	trip.ID = uuid.New()
	trip.Status = domain.TripStatusPending

	return s.repo.Create(ctx, trip)
}

// GetTrip retrieves a trip by its unique identifier
func (s *TripService) GetTrip(ctx context.Context, id uuid.UUID) (*domain.Trip, error) {
	trip, err := s.repo.GetByID(ctx, id)
	if err != nil {
		return nil, err // Returns domain.ErrTripNotFound if not found in repo
	}
	return trip, nil
}

// AssignDriver handles the business logic for assigning a driver to an existing trip
func (s *TripService) AssignDriver(ctx context.Context, tripID uuid.UUID, driverID uuid.UUID) error {
	// Validation check for driver_id using domain error
	if driverID == uuid.Nil {
		return domain.ErrInvalidTripData
	}

	// The repository handles the atomic update and state validation (status must be PENDING)
	err := s.repo.AssignDriver(ctx, tripID, driverID)
	if err != nil {
		return err // Will return domain.ErrInvalidTripStatus if already taken
	}

	return nil
}

// CheckHealth verifies the database connection status
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
