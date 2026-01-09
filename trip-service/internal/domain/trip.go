package domain

import (
	"errors"
	"time"

	"github.com/google/uuid"
)

// Business logic errors
var (
	ErrTripNotFound      = errors.New("trip not found")
	
	// Updated: Clarified message to cover both wrong status and "already assigned" cases
	ErrInvalidTripStatus = errors.New("trip is no longer available for assignment")
	
	// Split validation errors to ensure accurate API messages (400 Bad Request)
	ErrInvalidCreateTripData   = errors.New("invalid trip data: pickup, dropoff and passenger_id are required")
	
	// Specific to identity validation (Phase 3 & 4)
	ErrInvalidID               = errors.New("invalid trip or driver identity")
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
	// DriverID is validated in the service layer using domain.ErrInvalidID
	DriverID uuid.UUID `json:"driver_id"`
}
