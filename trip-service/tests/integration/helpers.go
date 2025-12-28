package integration

import (
	"net/http"
	"testing"
	"time"

	"github.com/UA-4697-DevOps/drive-ops/trip-service/internal/domain"
	"github.com/google/uuid"
	"gorm.io/gorm"
)

// CreateTestTrip creates a trip with test data for use in tests
func CreateTestTrip(passengerID uuid.UUID, pickup, dropoff string) *domain.Trip {
	now := time.Now()
	return &domain.Trip{
		ID:          uuid.New(),
		PassengerID: passengerID,
		DriverID:    nil,
		Pickup:      pickup,
		Dropoff:     dropoff,
		Status:      domain.TripStatusPending,
		CreatedAt:   now,
		UpdatedAt:   now,
	}
}

// AssertTripEqual compares two Trip objects and fails the test if they differ
func AssertTripEqual(t *testing.T, expected, actual *domain.Trip) {
	t.Helper()

	if expected.ID != actual.ID {
		t.Errorf("ID mismatch: expected %v, got %v", expected.ID, actual.ID)
	}
	if expected.PassengerID != actual.PassengerID {
		t.Errorf("PassengerID mismatch: expected %v, got %v", expected.PassengerID, actual.PassengerID)
	}
	if expected.Pickup != actual.Pickup {
		t.Errorf("Pickup mismatch: expected %v, got %v", expected.Pickup, actual.Pickup)
	}
	if expected.Dropoff != actual.Dropoff {
		t.Errorf("Dropoff mismatch: expected %v, got %v", expected.Dropoff, actual.Dropoff)
	}
	if expected.Status != actual.Status {
		t.Errorf("Status mismatch: expected %v, got %v", expected.Status, actual.Status)
	}

	// Compare DriverID (handle nil case)
	if (expected.DriverID == nil) != (actual.DriverID == nil) {
		t.Errorf("DriverID nil mismatch: expected %v, got %v", expected.DriverID, actual.DriverID)
	} else if expected.DriverID != nil && actual.DriverID != nil && *expected.DriverID != *actual.DriverID {
		t.Errorf("DriverID mismatch: expected %v, got %v", *expected.DriverID, *actual.DriverID)
	}
}

// ClearTestData removes all data from the trips table
func ClearTestData(db *gorm.DB) error {
	return db.Exec("TRUNCATE TABLE trips CASCADE").Error
}

// MakeHTTPRequest makes an HTTP request for testing endpoints
func MakeHTTPRequest(method, url string) (*http.Response, error) {
	client := &http.Client{
		Timeout: 10 * time.Second,
	}

	req, err := http.NewRequest(method, url, nil)
	if err != nil {
		return nil, err
	}

	return client.Do(req)
}
