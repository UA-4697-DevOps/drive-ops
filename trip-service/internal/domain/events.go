package domain

import (
	"time"
)

// Location describes the coordinates and address for a trip
type Location struct {
	Address string  `json:"address"`
	Lat     float64 `json:"lat"`
	Lng     float64 `json:"lng"`
}

// BaseEvent contains metadata common to all events
type BaseEvent struct {
	EventID       string    `json:"eventId"`       // Unique event identifier
	EventType     string    `json:"eventType"`     // e.g., trip.created
	EventVersion  string    `json:"version"`       // Schema version
	CorrelationID string    `json:"correlationId"` // Used for distributed tracing
	Timestamp     time.Time `json:"timestamp"`     // Time when the event occurred
}

// TripCreatedEvent corresponds to the trip.created schema
type TripCreatedEvent struct {
	BaseEvent
	Payload struct {
		TripID      string    `json:"tripId"`      
		PassengerID string    `json:"passengerId"` 
		Pickup      Location  `json:"pickup"`
		Dropoff     Location  `json:"dropoff"`
		CreatedAt   time.Time `json:"createdAt"`   
	} `json:"payload"`
}

// DriverAssignedEvent corresponds to the driver.assigned schema
type DriverAssignedEvent struct {
	BaseEvent
	Payload struct {
		TripID     string    `json:"tripId"`     
		DriverID   string    `json:"driverId"`   
		AssignedAt time.Time `json:"assignedAt"` 
	} `json:"payload"`
}

// TripCompletedEvent corresponds to the trip.completed schema
type TripCompletedEvent struct {
	BaseEvent
	Payload struct {
		TripID      string    `json:"tripId"`      
		DriverID    string    `json:"driverId"`    
		CompletedAt time.Time `json:"completedAt"` 
	} `json:"payload"`
}
