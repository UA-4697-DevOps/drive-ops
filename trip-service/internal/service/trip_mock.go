package service

import (
	"context"
	"trip-service/internal/domain"

	"github.com/google/uuid"
)

// MockTripService імітує роботу справжнього сервісу
type MockTripService struct{}

func (m *MockTripService) CreateTrip(ctx context.Context, trip *domain.Trip) error {
	trip.ID = uuid.New()
	trip.Status = "MOCKED_PENDING"
	return nil // Завжди успіх
}

func (m *MockTripService) GetTrip(ctx context.Context, id uuid.UUID) (*domain.Trip, error) {
	return &domain.Trip{
		ID:     id,
		Pickup: "Zahlushka Street 1",
		Status: "COMPLETED",
	}, nil
}

func (m *MockTripService) CheckHealth(ctx context.Context) error {
	return nil // База "завжди здорова"
}
