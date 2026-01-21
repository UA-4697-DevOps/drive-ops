package broker

import (
	"time"

	"github.com/google/uuid"
	"trip-service/internal/domain"
)

// simpleGeocode provides basic geocoding for Kyiv addresses (MVP/demo)
func simpleGeocode(address string) (lat, lng float64) {
	// Default to Khreshchatyk center if no match
	defaultLat, defaultLng := 50.4501, 30.5234

	// Simple pattern matching for demo purposes
	// In production, use a proper geocoding service
	if len(address) > 0 {
		// All addresses in Kyiv center area (Khreshchatyk)
		return defaultLat, defaultLng
	}

	return defaultLat, defaultLng
}

// BuildTripCreatedEvent constructs a TripCreatedEvent from a Trip
func BuildTripCreatedEvent(trip *domain.Trip, correlationID string) *domain.TripCreatedEvent {
	event := &domain.TripCreatedEvent{}

	// Set base event metadata
	event.EventID = uuid.New().String()
	event.EventType = "trip.event.created"
	event.EventVersion = "1.0"
	event.CorrelationID = correlationID
	event.Timestamp = time.Now()

	// Set payload
	event.Payload.TripID = trip.ID.String()
	event.Payload.PassengerID = trip.PassengerID.String()
	event.Payload.CreatedAt = trip.CreatedAt

	// MVP: Use simple geocoding for demo (Kyiv coordinates)
	// TODO: Integrate proper geocoding service (Google Maps, etc.)
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
