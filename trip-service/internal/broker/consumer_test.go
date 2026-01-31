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

func (m *MockTripService) CompleteTrip(ctx context.Context, tripID uuid.UUID) error {
	args := m.Called(ctx, tripID)
	return args.Error(0)
}

func (m *MockTripService) CheckHealth(ctx context.Context) error {
	args := m.Called(ctx)
	return args.Error(0)
}

func TestRabbitMQConsumer_HandleDriverAssigned(t *testing.T) {
	mockSvc := new(MockTripService)
	consumer := &RabbitMQConsumer{
		service: mockSvc,
	}

	t.Run("Success", func(t *testing.T) {
		tripID := uuid.New()
		driverID := uuid.New()
		
		// [SYNCED] Using updated domain structs. 
		// json.Marshal will now produce camelCase keys automatically.
		event := domain.DriverAssignedEvent{
			BaseEvent: domain.BaseEvent{
				EventID:   uuid.New().String(),
				EventType: "driver.assigned",
				Timestamp: time.Now().UTC(),
			},
		}
		event.Payload.TripID = tripID.String()
		event.Payload.DriverID = driverID.String()
		
		body, _ := json.Marshal(event)

		mockSvc.On("AssignDriver", mock.Anything, tripID, driverID).Return(nil).Once()

		err := consumer.handleDriverAssigned(context.Background(), body)
		assert.NoError(t, err)

		mockSvc.AssertExpectations(t)
	})

	t.Run("Invalid JSON", func(t *testing.T) {
		err := consumer.handleDriverAssigned(context.Background(), []byte("invalid json"))
		assert.Error(t, err)
		assert.Contains(t, err.Error(), "unmarshal JSON")
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

func TestRabbitMQConsumer_HandleTripCompleted(t *testing.T) {
	mockSvc := new(MockTripService)
	consumer := &RabbitMQConsumer{
		service: mockSvc,
	}

	t.Run("Success", func(t *testing.T) {
		tripID := uuid.New()
		driverID := uuid.New()

		// [SYNCED] json.Marshal uses the new camelCase tags from domain.events.go
		event := domain.TripCompletedEvent{
			BaseEvent: domain.BaseEvent{
				EventID:   uuid.New().String(),
				EventType: "trip.completed",
				Timestamp: time.Now().UTC(),
			},
		}
		event.Payload.TripID = tripID.String()
		event.Payload.DriverID = driverID.String()
		event.Payload.CompletedAt = time.Now().UTC()

		body, _ := json.Marshal(event)

		mockSvc.On("CompleteTrip", mock.Anything, tripID).Return(nil).Once()

		err := consumer.handleTripCompleted(context.Background(), body)
		assert.NoError(t, err)

		mockSvc.AssertExpectations(t)
	})

	t.Run("Invalid JSON", func(t *testing.T) {
		err := consumer.handleTripCompleted(context.Background(), []byte("invalid json"))
		assert.Error(t, err)
		assert.Contains(t, err.Error(), "unmarshal JSON")
	})

	t.Run("Invalid Trip ID", func(t *testing.T) {
		event := domain.TripCompletedEvent{}
		event.Payload.TripID = "not-a-uuid"
		event.Payload.DriverID = uuid.New().String()

		body, _ := json.Marshal(event)

		err := consumer.handleTripCompleted(context.Background(), body)
		assert.Error(t, err)
		assert.Contains(t, err.Error(), "invalid trip ID")
	})
}
