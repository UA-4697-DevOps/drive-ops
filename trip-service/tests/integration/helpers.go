package integration

import (
    "bytes"
    "encoding/json"
    "fmt"
    "net/http"
    "testing"
    "time"
    "trip-service/internal/domain"

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
        t.Errorf("Pickup mismatch: expected %s, got %s", expected.Pickup, actual.Pickup)
    }
    if expected.Dropoff != actual.Dropoff {
        t.Errorf("Dropoff mismatch: expected %s, got %s", expected.Dropoff, actual.Dropoff)
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

// ClearTestData removes all data from the trips table using TRUNCATE for speed
func ClearTestData(db *gorm.DB) error {
    return db.Exec("TRUNCATE TABLE trips CASCADE").Error
}

// MakeHTTPRequest makes an HTTP request with a 10s timeout
func MakeHTTPRequest(method, url string) (*http.Response, error) {
    client := &http.Client{
        Timeout: 10 * time.Second,
    }

    req, err := http.NewRequest(method, url, nil)
    if err != nil {
        return nil, fmt.Errorf("failed to create request: %w", err)
    }

    return client.Do(req)
}

// [NEW] MakeJSONRequest specifically handles camelCase payloads for Trip Service endpoints
func MakeJSONRequest(method, url string, payload interface{}) (*http.Response, error) {
    client := &http.Client{
        Timeout: 10 * time.Second,
    }

    // Ensure we marshal the payload to JSON
    jsonBody, err := json.Marshal(payload)
    if err != nil {
        return nil, fmt.Errorf("failed to marshal payload: %w", err)
    }

    req, err := http.NewRequest(method, url, bytes.NewBuffer(jsonBody))
    if err != nil {
        return nil, fmt.Errorf("failed to create request: %w", err)
    }

    req.Header.Set("Content-Type", "application/json")
    return client.Do(req)
}
