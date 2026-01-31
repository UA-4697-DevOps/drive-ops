package integration

import (
	"fmt"
	"log"
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

// MakeHTTPRequest makes an HTTP request with a retry mechanism for container boot time
func MakeHTTPRequest(method, url string) (*http.Response, error) {
    client := &http.Client{
        Timeout: 5 * time.Second,
    }

    var resp *http.Response
    var err error // Outer variable to store the execution error

    for i := 0; i < 5; i++ {
        // Use reqErr to avoid shadowing the main err variable
        req, reqErr := http.NewRequest(method, url, nil)
        if reqErr != nil {
            return nil, reqErr
        }

        resp, err = client.Do(req) // Assign execution error to the outer err variable
        if err == nil {
            return resp, nil
        }
		// CodeRabbit Fix: Close body if it exists to prevent resource leaks
		if resp != nil && resp.Body != nil {
    		_ = resp.Body.Close()
		}

        log.Printf("Attempt %d: Service at %s not ready yet, retrying...", i+1, url)
		
        if i < 4 {
    		time.Sleep(2 * time.Second)
		}
    }

    // Now err is guaranteed to contain the last error from client.Do(req)
    return nil, fmt.Errorf("service at %s failed to respond after 5 attempts: %w", url, err)
}
