package broker

import (
	"time"

	"github.com/google/uuid"
	"trip-service/internal/domain"
)

// simpleGeocode provides basic geocoding for Kyiv addresses (MVP/demo)
func simpleGeocode(address string) (lat, lng float64) {
	// Kyiv city center defaults
	defaultLat, defaultLng := 50.4501, 30.5234
	return defaultLat, defaultLng
}

// BuildTripCreatedEvent constructs a TripCreatedEvent from a Trip.
// [CRITICAL] Ensure domain.TripCreatedEvent has json:"camelCase" tags.
func BuildTripCreatedEvent(trip *domain.Trip, correlationID string) *domain.TripCreatedEvent {
	event := &domain.TripCreatedEvent{}

	// Envelope Fields - Standardized for cross-service compatibility
	event.EventID = uuid.New().String()
	event.EventType = "trip.created" 
	event.EventVersion = "1.0"
	event.CorrelationID = correlationID
	event.Timestamp = time.Now().UTC()

	// Payload Mapping
	event.Payload.TripID = trip.ID.String()
	event.Payload.PassengerID = trip.PassengerID.String()
	event.Payload.CreatedAt = trip.CreatedAt

	pickupLat, pickupLng := simpleGeocode(trip.Pickup)
	dropoffLat, dropoffLng := simpleGeocode(trip.Dropoff)

	event.Payload.Pickup = domain.Location{
		Address: trip.Pickup,
		Lat:     pickupLat,
		Lng:     pickupLng,
	}

	event.Payload.Dropoff = domain.Location{
		Address: trip.Dropoff,
		Lat:     dropoffLat,
		Lng:     dropoffLng,
	}

	return event
}

// DriverAssignedEvent strictly matches the "driver.assigned" payload.
// These tags ensure the Go Trip Service can READ what the Python Driver Service SENDS.
type DriverAssignedEvent struct {
	Version       string    `json:"version"`
	MessageID     string    `json:"messageId"`
	Timestamp     time.Time `json:"timestamp"`
	CorrelationID string    `json:"correlationId"`
	EventType     string    `json:"eventType"`
	Source        string    `json:"source"`
	Payload       struct {
		TripID      string `json:"tripId"`      // Must match Python key
		DriverID    string `json:"driverId"`    // Must match Python key
		DriverName  string `json:"driverName"`
		VehicleInfo struct {
			Make         string `json:"make"`
			Model        string `json:"model"`
			LicensePlate string `json:"licensePlate"`
		} `json:"vehicleInfo"`
		AssignedAt time.Time `json:"assignedAt"`
	} `json:"payload"`
}
