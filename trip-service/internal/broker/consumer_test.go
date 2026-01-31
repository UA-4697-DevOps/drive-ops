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

// [FIX] Renamed to test SQSConsumer
func TestSQSConsumer_HandleDriverAssigned(t *testing.T) {
    mockSvc := new(MockTripService)
    // [FIX] Using SQSConsumer instead of RabbitMQConsumer
    consumer := &SQSConsumer{
        service: mockSvc,
    }

    t.Run("Success with camelCase JSON", func(t *testing.T) {
        tripID := uuid.New()
        driverID := uuid.New()
        
        // [FIX] Simulating the EXACT JSON structure sent by Python service
        // We use a raw string to verify our 'json' tags handle camelCase correctly.
        jsonPayload := `{
            "eventType": "driver.assigned",
            "payload": {
                "tripId": "` + tripID.String() + `",
                "driverId": "` + driverID.String() + `"
            }
        }`

        mockSvc.On("AssignDriver", mock.Anything, tripID, driverID).Return(nil).Once()

        err := consumer.handleDriverAssigned(context.Background(), []byte(jsonPayload))
        assert.NoError(t, err)
        mockSvc.AssertExpectations(t)
    })

    t.Run("Invalid JSON", func(t *testing.T) {
        err := consumer.handleDriverAssigned(context.Background(), []byte("invalid json"))
        assert.Error(t, err)
        assert.Contains(t, err.Error(), "failed to unmarshal JSON")
    })
}

func TestSQSConsumer_HandleTripCompleted(t *testing.T) {
    mockSvc := new(MockTripService)
    consumer := &SQSConsumer{
        service: mockSvc,
    }

    t.Run("Success with camelCase JSON", func(t *testing.T) {
        tripID := uuid.New()

        // [FIX] Updated EventType to match production "trip.completed"
        jsonPayload := `{
            "eventType": "trip.completed",
            "payload": {
                "tripId": "` + tripID.String() + `",
                "status": "COMPLETED"
            }
        }`

        mockSvc.On("CompleteTrip", mock.Anything, tripID).Return(nil).Once()

        err := consumer.handleTripCompleted(context.Background(), []byte(jsonPayload))
        assert.NoError(t, err)
        mockSvc.AssertExpectations(t)
    })
}
