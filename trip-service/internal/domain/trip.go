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
	// Added to handle validation errors and return 400 Bad Request
	ErrInvalidTripData   = errors.New("invalid trip data: pickup, dropoff and passenger_id are required")
)

// Trip status constants for lifecycle management
const (
	TripStatusPending    = "PENDING"
	TripStatusConfirmed  = "CONFIRMED"
	TripStatusActive     = "ACTIVE"
	TripStatusInProgress = "IN_PROGRESS"
	TripStatusCompleted  = "COMPLETED"
	TripStatusCancelled  = "CANCELLED"
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
	// Updated: Removed the "validate" tag because validation is handled in the service layer
	DriverID uuid.UUID `json:"driver_id"`
}
