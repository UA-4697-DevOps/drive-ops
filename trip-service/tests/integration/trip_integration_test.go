package integration

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"testing"
	"time"

	"trip-service/internal/domain"
	"trip-service/internal/repository"

	"github.com/google/uuid"
)

// TestDatabaseConnection verifies that we can connect to PostgreSQL
func TestDatabaseConnection(t *testing.T) {
	if testDB == nil {
		t.Fatal("Test database connection is nil")
	}

	sqlDB, err := testDB.DB()
	if err != nil {
		t.Fatalf("Failed to get underlying sql.DB: %v", err)
	}

	if err := sqlDB.Ping(); err != nil {
		t.Fatalf("Failed to ping database: %v", err)
	}

	t.Log("Successfully connected to test database")
}

// TestDatabaseMigrations verifies that migrations were applied correctly
func TestDatabaseMigrations(t *testing.T) {
	// Check if trips table exists
	var exists bool
	query := `
		SELECT EXISTS (
			SELECT FROM information_schema.tables
			WHERE table_schema = 'public'
			AND table_name = 'trips'
		)
	`
	if err := testDB.Raw(query).Scan(&exists).Error; err != nil {
		t.Fatalf("Failed to check if trips table exists: %v", err)
	}

	if !exists {
		t.Fatal("trips table does not exist after migrations")
	}

	// Check if trip_status enum exists
	query = `
		SELECT EXISTS (
			SELECT 1 FROM pg_type WHERE typname = 'trip_status'
		)
	`
	if err := testDB.Raw(query).Scan(&exists).Error; err != nil {
		t.Fatalf("Failed to check if trip_status enum exists: %v", err)
	}

	if !exists {
		t.Fatal("trip_status enum does not exist after migrations")
	}

	// Check if index exists
	query = `
		SELECT EXISTS (
			SELECT 1 FROM pg_indexes
			WHERE tablename = 'trips'
			AND indexname = 'idx_trips_passenger_id'
		)
	`
	if err := testDB.Raw(query).Scan(&exists).Error; err != nil {
		t.Fatalf("Failed to check if index exists: %v", err)
	}

	if !exists {
		t.Fatal("idx_trips_passenger_id index does not exist after migrations")
	}

	t.Log("All migrations applied successfully")
}

// TestTripRepository_Create tests creating a new trip
func TestTripRepository_Create(t *testing.T) {
    repo := repository.NewTripRepository(testDB)
    ctx := context.Background()

    // 1. Arrange: Prepare test data
    passengerID := uuid.New()
    trip := CreateTestTrip(passengerID, "Kyiv, Khreshchatyk St", "Kyiv, Maidan Nezalezhnosti")

    // 2. Clean up: Ensure the trip is removed regardless of test outcome
    t.Cleanup(func() {
        testDB.Exec("DELETE FROM trips WHERE id = ?", trip.ID)
    })

    // 3. Act: Execute the repository method
    err := repo.Create(ctx, trip)
    if err != nil {
        t.Fatalf("Failed to create trip: %v", err)
    }

    // 4. Assert: Verify the data in the database matches our expectations
    var createdTrip domain.Trip
    if err := testDB.First(&createdTrip, "id = ?", trip.ID).Error; err != nil {
        t.Fatalf("Failed to find created trip in database: %v", err)
    }

    // Use the optimized helper to check all fields (Status, UUIDs, Casing)
    // This is more robust than manual if-checks for every field.
    AssertTripEqual(t, trip, &createdTrip)

    t.Log("Successfully created trip and verified all fields match")
}

// TestTripRepository_GetByID tests retrieving a trip by ID
func TestTripRepository_GetByID(t *testing.T) {
	repo := repository.NewTripRepository(testDB)
	ctx := context.Background()

	passengerID := uuid.New()
	trip := CreateTestTrip(passengerID, "Lviv, Rynok Square", "Lviv, High Castle")

	// Create test trip
	if err := testDB.Create(trip).Error; err != nil {
		t.Fatalf("Failed to create test trip: %v", err)
	}

	// Clean up after test
	t.Cleanup(func() {
		testDB.Exec("DELETE FROM trips WHERE id = ?", trip.ID)
	})

	// Get trip by ID
	retrieved, err := repo.GetByID(ctx, trip.ID)
	if err != nil {
		t.Fatalf("Failed to get trip by ID: %v", err)
	}

	if retrieved == nil {
		t.Fatal("Retrieved trip is nil")
	}

	// Verify fields
	AssertTripEqual(t, trip, retrieved)

	t.Log("Successfully retrieved trip by ID")
}

// TestTripRepository_Update tests updating a trip
func TestTripRepository_Update(t *testing.T) {
    repo := repository.NewTripRepository(testDB)
    ctx := context.Background()

    passengerID := uuid.New()
    driverID := uuid.New()
    // Using the helper to create a PENDING trip first
    trip := CreateTestTrip(passengerID, "Odesa, Deribasivska St", "Odesa, Arcadia Beach")

    // Create initial state in DB
    if err := testDB.Create(trip).Error; err != nil {
        t.Fatalf("Failed to create test trip: %v", err)
    }

    t.Cleanup(func() {
        testDB.Exec("DELETE FROM trips WHERE id = ?", trip.ID)
    })

    // Update trip fields
    trip.DriverID = &driverID
    trip.Status = domain.TripStatusActive // Use domain constant for safety
    trip.UpdatedAt = time.Now()

    // Act
    err := repo.Update(ctx, trip)
    if err != nil {
        t.Fatalf("Failed to update trip: %v", err)
    }

    // Verify
    var updated domain.Trip
    if err := testDB.First(&updated, "id = ?", trip.ID).Error; err != nil {
        t.Fatalf("Failed to find updated trip: %v", err)
    }

    // Comprehensive assertion including pointer-to-uuid and status
    AssertTripEqual(t, trip, &updated)

    t.Log("Successfully updated trip status and assigned driver")
}

// TestTripRepository_Delete tests deleting a trip
func TestTripRepository_Delete(t *testing.T) {
	repo := repository.NewTripRepository(testDB)
	ctx := context.Background()

	passengerID := uuid.New()
	trip := CreateTestTrip(passengerID, "Kharkiv, Freedom Square", "Kharkiv, Gorky Park")

	// Create test trip
	if err := testDB.Create(trip).Error; err != nil {
		t.Fatalf("Failed to create test trip: %v", err)
	}

	// Delete trip
	err := repo.Delete(ctx, trip.ID)
	if err != nil {
		t.Fatalf("Failed to delete trip: %v", err)
	}

	// Verify deletion
	var deleted domain.Trip
	err = testDB.First(&deleted, "id = ?", trip.ID).Error
	if err == nil {
		t.Error("Trip still exists after deletion")
	}

	t.Log("Successfully deleted trip")
}

// TestHealthEndpoint tests the health check endpoint
func TestHealthEndpoint(t *testing.T) {
    // 1. Dynamic URL: Respect the SERVICE_URL from CI or fallback to localhost
    baseURL := getEnv("SERVICE_URL", "http://localhost:8081")
    healthURL := fmt.Sprintf("%s/health", baseURL)

    // 2. Resilience: Use the MakeHTTPRequest helper with built-in retries
    resp, err := MakeHTTPRequest("GET", healthURL)
    if err != nil {
        t.Fatalf("Failed to reach health endpoint at %s: %v", healthURL, err)
    }
    defer func() { _ = resp.Body.Close() }()

    // 3. Status Validation
    if resp.StatusCode != http.StatusOK {
        t.Errorf("Expected status 200, got %d", resp.StatusCode)
    }

    // 4. Body Verification
    body, err := io.ReadAll(resp.Body)
    if err != nil {
        t.Fatalf("Failed to read response body: %v", err)
    }

    var health map[string]interface{}
    if err := json.Unmarshal(body, &health); err != nil {
        t.Fatalf("Failed to decode JSON: %v. Body was: %s", err, string(body))
    }

    // 5. Mock Mode Confirmation
    // If 'status' is 'ok', it confirms the Mock SQS and Postgres initialized correctly.
    status, ok := health["status"]
    if !ok || status != "ok" {
        t.Errorf("Health status check failed. Expected 'ok', got '%v'. Body: %s", status, string(body))
    }

    if detail, ok := health["detail"]; ok {
        t.Logf("Health Details: %v", detail)
    }

    t.Logf("Health endpoint check successful for %s", healthURL)
}
