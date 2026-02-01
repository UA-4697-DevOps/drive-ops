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
    var lastErr error 
    
    const maxAttempts = 25 

    for i := 0; i < maxAttempts; i++ {
        req, err := http.NewRequest(method, url, nil)
        if err != nil {
            return nil, err
        }

        resp, lastErr = client.Do(req) 
        if lastErr == nil {
            // Check for 503 which happens if the proxy is up but the app isn't
            if resp.StatusCode == http.StatusServiceUnavailable {
                _ = resp.Body.Close()
                
                // 1. Set lastErr so the final return knows WHY it failed
                lastErr = fmt.Errorf("service returned 503 Service Unavailable")
                
                log.Printf("Attempt %d: Service at %s returned 503, retrying...", i+1, url)
                
                // 2. Skip sleep on the very last attempt
                if i < maxAttempts-1 {
                    time.Sleep(2 * time.Second)
                }
                continue
            }
            return resp, nil
        }

        if resp != nil && resp.Body != nil {
            _ = resp.Body.Close()
        }

        log.Printf("Attempt %d: Service at %s not ready yet, retrying: %v", i+1, url, lastErr)
        
        // 3. Keep the error branch sleep aligned too
        if i < maxAttempts-1 {
            time.Sleep(2 * time.Second)
        }
    }

    // Now if it fails after 25 attempts, lastErr will correctly say "returned 503" 
    // instead of "connection refused" if the last attempt was a 503.
    return nil, fmt.Errorf("service at %s failed after %d attempts: %w", url, maxAttempts, lastErr)
}
