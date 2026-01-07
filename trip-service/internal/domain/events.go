package domain

import (
	"time"
)

// Location описує координати для поїздки
type Location struct {
	Address string  `json:"address"`
	Lat     float64 `json:"lat"`
	Lng     float64 `json:"lng"`
}

// BaseEvent містить метадані, спільні для всіх подій
type BaseEvent struct {
	EventID       string    `json:"event_id"`
	EventType     string    `json:"event_type"`    // Напр. trip.event.created
	EventVersion  string    `json:"event_version"`
	CorrelationID string    `json:"correlation_id"`
	Timestamp     time.Time `json:"timestamp"`
}

// TripCreatedEvent відповідає схемі trip.event.created
type TripCreatedEvent struct {
	BaseEvent
	Payload struct {
		TripID      string    `json:"trip_id"`
		PassengerID string    `json:"passenger_id"`
		Pickup      Location  `json:"pickup"`
		Dropoff     Location  `json:"dropoff"`
		CreatedAt   time.Time `json:"created_at"`
	} `json:"payload"`
}

// DriverAssignedEvent відповідає схемі trip.event.driver_assigned
type DriverAssignedEvent struct {
	BaseEvent
	Payload struct {
		TripID     string    `json:"trip_id"`
		DriverID   string    `json:"driver_id"`
		AssignedAt time.Time `json:"assigned_at"`
	} `json:"payload"`
}
