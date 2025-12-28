package integration

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"testing"
	"time"

	"github.com/UA-4697-DevOps/drive-ops/trip-service/internal/domain"
	"github.com/UA-4697-DevOps/drive-ops/trip-service/internal/repository"
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

	passengerID := uuid.New()
	trip := CreateTestTrip(passengerID, "Kyiv, Khreshchatyk St", "Kyiv, Maidan Nezalezhnosti")

	// Clean up after test
	t.Cleanup(func() {
		testDB.Exec("DELETE FROM trips WHERE id = ?", trip.ID)
	})

	// Create trip
	err := repo.Create(ctx, trip)
	if err != nil {
		t.Fatalf("Failed to create trip: %v", err)
	}

	// Verify trip was created
	var createdTrip domain.Trip
	if err := testDB.First(&createdTrip, "id = ?", trip.ID).Error; err != nil {
		t.Fatalf("Failed to find created trip: %v", err)
	}

	// Verify fields
	if createdTrip.PassengerID != passengerID {
		t.Errorf("Expected passenger_id %v, got %v", passengerID, createdTrip.PassengerID)
	}
	if createdTrip.Pickup != "Kyiv, Khreshchatyk St" {
		t.Errorf("Expected pickup 'Kyiv, Khreshchatyk St', got '%s'", createdTrip.Pickup)
	}
	if createdTrip.Status != "PENDING" {
		t.Errorf("Expected status 'PENDING', got '%s'", createdTrip.Status)
	}

	t.Log("Successfully created trip")
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
	trip := CreateTestTrip(passengerID, "Odesa, Deribasivska St", "Odesa, Arcadia Beach")

	// Create test trip
	if err := testDB.Create(trip).Error; err != nil {
		t.Fatalf("Failed to create test trip: %v", err)
	}

	// Clean up after test
	t.Cleanup(func() {
		testDB.Exec("DELETE FROM trips WHERE id = ?", trip.ID)
	})

	// Update trip
	trip.DriverID = &driverID
	trip.Status = "ACTIVE"
	trip.UpdatedAt = time.Now()

	err := repo.Update(ctx, trip)
	if err != nil {
		t.Fatalf("Failed to update trip: %v", err)
	}

	// Verify update
	var updated domain.Trip
	if err := testDB.First(&updated, "id = ?", trip.ID).Error; err != nil {
		t.Fatalf("Failed to find updated trip: %v", err)
	}

	if updated.Status != "ACTIVE" {
		t.Errorf("Expected status 'ACTIVE', got '%s'", updated.Status)
	}
	if updated.DriverID == nil {
		t.Error("Expected driver_id to be set, got nil")
	} else if *updated.DriverID != driverID {
		t.Errorf("Expected driver_id %v, got %v", driverID, *updated.DriverID)
	}

	t.Log("Successfully updated trip")
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
	//t.Skip("Skipping health endpoint test - HTTP server not yet implemented")

	resp, err := MakeHTTPRequest("GET", "http://localhost:5002/health")
	if err != nil {
		t.Fatalf("Failed to make health check request: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		t.Errorf("Expected status 200, got %d", resp.StatusCode)
	}

	// Parse and verify response body
	var health map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&health); err != nil {
		// Read the body to see what we actually got
		resp.Body.Close()
		resp, _ = MakeHTTPRequest("GET", "http://localhost:5002/health")
		body, _ := io.ReadAll(resp.Body)
		t.Fatalf("Failed to decode response: %v. Body was: %s", err, string(body))
	}

	if status, ok := health["status"]; !ok || status != "ok" {
		t.Errorf("Expected status 'ok', got %v", status)
	}

	t.Log("Health endpoint returned 200 OK")

}
