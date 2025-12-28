package service

import (
	"context"
	"errors"
	"fmt"

	"github.com/UA-4697-DevOps/drive-ops/trip-service/internal/domain"
	"github.com/UA-4697-DevOps/drive-ops/trip-service/internal/repository"

	"github.com/google/uuid"
	"gorm.io/gorm"
)

var (
	ErrTripNotFound = errors.New("trip not found")
	ErrInvalidInput = errors.New("pickup and dropoff locations are required")
)

type TripService struct {
	repo *repository.TripRepository
}

func NewTripService(repo *repository.TripRepository) *TripService {
	return &TripService{repo: repo}
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

	return s.repo.Create(ctx, trip)
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
