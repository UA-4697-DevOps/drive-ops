package broker

import (
	"time"

	"github.com/google/uuid"
	"trip-service/internal/domain"
)

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

	// TODO: For MVP, we only set address. Lat/Lng coordinates should be added
	// when geocoding service is integrated or when client sends coordinates.
	event.Payload.Pickup = domain.Location{
		Address: trip.Pickup,
		Lat:     0, // Will be populated when geocoding is added
		Lng:     0,
	}

	event.Payload.Dropoff = domain.Location{
		Address: trip.Dropoff,
		Lat:     0, // Will be populated when geocoding is added
		Lng:     0,
	}

	return event
}
