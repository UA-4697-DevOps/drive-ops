package domain

import (
	"time"

	"github.com/google/uuid"
)

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

const (
	TripStatusPending    = "PENDING"
	TripStatusConfirmed  = "CONFIRMED"
	TripStatusInProgress = "IN_PROGRESS"
	TripStatusCompleted  = "COMPLETED"
	TripStatusCancelled  = "CANCELLED"
)
