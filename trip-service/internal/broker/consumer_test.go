package broker

import (
	"context"
	"encoding/json"
	"testing"
	"time"

	"trip-service/internal/domain"

	"github.com/google/uuid"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/mock"
)

// MockTripService for testing
type MockTripService struct {
	mock.Mock
}

func (m *MockTripService) CreateTrip(ctx context.Context, trip *domain.Trip) error {
	args := m.Called(ctx, trip)
	return args.Error(0)
}

func (m *MockTripService) GetTrip(ctx context.Context, id uuid.UUID) (*domain.Trip, error) {
	args := m.Called(ctx, id)
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).(*domain.Trip), args.Error(1)
}

func (m *MockTripService) AssignDriver(ctx context.Context, tripID uuid.UUID, driverID uuid.UUID) error {
	args := m.Called(ctx, tripID, driverID)
	return args.Error(0)
}

func (m *MockTripService) CheckHealth(ctx context.Context) error {
	args := m.Called(ctx)
	return args.Error(0)
}

func TestRabbitMQConsumer_HandleDriverAssigned(t *testing.T) {
	// Setup generic mock service
	mockSvc := new(MockTripService)
	consumer := &RabbitMQConsumer{
		service: mockSvc,
	}

	t.Run("Success", func(t *testing.T) {
		tripID := uuid.New()
		driverID := uuid.New()
		
		// Create a valid event payload
		event := domain.DriverAssignedEvent{
			BaseEvent: domain.BaseEvent{
				EventType: "trip.event.driver_assigned",
				Timestamp: time.Now(),
			},
		}
		event.Payload.TripID = tripID.String()
		event.Payload.DriverID = driverID.String()
		
		body, _ := json.Marshal(event)

		// Expect AssignDriver to be called
		mockSvc.On("AssignDriver", mock.Anything, tripID, driverID).Return(nil).Once()

		// Execute
		err := consumer.handleDriverAssigned(context.Background(), body)
		assert.NoError(t, err)

		mockSvc.AssertExpectations(t)
	})

	t.Run("Invalid JSON", func(t *testing.T) {
		err := consumer.handleDriverAssigned(context.Background(), []byte("invalid json"))
		assert.Error(t, err)
		assert.Contains(t, err.Error(), "failed to unmarshal JSON")
	})

	t.Run("Invalid IDs", func(t *testing.T) {
		event := domain.DriverAssignedEvent{}
		event.Payload.TripID = "not-a-uuid"
		event.Payload.DriverID = uuid.New().String()
		
		body, _ := json.Marshal(event)

		err := consumer.handleDriverAssigned(context.Background(), body)
		assert.Error(t, err)
		assert.Contains(t, err.Error(), "invalid trip ID")
	})
}
