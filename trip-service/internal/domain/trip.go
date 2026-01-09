package domain

import (
	"errors"
	"time"

	"github.com/google/uuid"
)

// Business logic errors
var (
	ErrTripNotFound      = errors.New("trip not found")
	ErrInvalidTripStatus = errors.New("trip is not in PENDING status")
	// ErrInvalidTripData handles validation errors to return 400 Bad Request
	ErrInvalidTripData   = errors.New("invalid trip data: pickup, dropoff and passenger_id are required")
)

// Trip status constants for lifecycle management
const (
	// TripStatusPending: Passenger created a request, searching for drivers
	TripStatusPending   = "PENDING"
	// TripStatusConfirmed: Driver accepted the request, moving to pickup point
	TripStatusConfirmed = "CONFIRMED"
	// TripStatusActive: Trip is currently in progress (passenger is in the vehicle)
	TripStatusActive    = "ACTIVE"
	// TripStatusCompleted: Trip finished successfully
	TripStatusCompleted = "COMPLETED"
	// TripStatusCancelled: Trip was aborted by passenger or driver
	TripStatusCancelled = "CANCELLED"
)

// Trip represents the main database model for a ride
type Trip struct {
	ID          uuid.UUID  `gorm:"primaryKey;type:uuid" json:"id"`
	PassengerID uuid.UUID  `gorm:"type:uuid;not null" json:"passenger_id"`
	DriverID    *uuid.UUID `gorm:"type:uuid" json:"driver_id,omitempty"`
	Pickup      string     `gorm:"not null" json:"pickup"`
	Dropoff     string     `gorm:"not null" json:"dropoff"`
	Status      string     `gorm:"type:trip_status;default:'PENDING'" json:"status"`
	CreatedAt   time.Time  `json:"created_at"`
	UpdatedAt   time.Time  `json:"updated_at"`
}

// AssignDriverRequest represents the Data Transfer Object (DTO) for the API input
type AssignDriverRequest struct {
	// DriverID is validated in the service layer
	DriverID uuid.UUID `json:"driver_id"`
}
