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
// Standardizes the envelope fields for SQS FIFO delivery.
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
