package repository

import (
	"context"
	"testing"
	"time"
	"trip-service/internal/domain"

	"github.com/google/uuid"
	"github.com/stretchr/testify/assert"
	"github.com/testcontainers/testcontainers-go"
	"github.com/testcontainers/testcontainers-go/modules/postgres"
	"github.com/testcontainers/testcontainers-go/wait"
	gormPostgres "gorm.io/driver/postgres"
	"gorm.io/gorm"
)

// setupTestDB initializes a temporary Postgres container for testing purposes
func setupTestDB(t *testing.T) (*gorm.DB, func()) {
	ctx := context.Background()

	// 1. Setup and start the Postgres container (using 15-alpine for faster startup)
	pgContainer, err := postgres.Run(ctx,
		"postgres:15-alpine",
		postgres.WithDatabase("trip_service_test"),
		postgres.WithUsername("testuser"),
		postgres.WithPassword("testpass"),
		testcontainers.WithWaitStrategy(
			wait.ForLog("database system is ready to accept connections").
				WithOccurrence(2).
				WithStartupTimeout(30*time.Second)),
	)
	if err != nil {
		t.Fatalf("Failed to start postgres container: %v", err)
	}

	// Get the connection string
	connStr, err := pgContainer.ConnectionString(ctx, "sslmode=disable")
	if err != nil {
		t.Fatalf("Failed to get connection string: %v", err)
	}

	// 2. Connect GORM to the container instance
	db, err := gorm.Open(gormPostgres.Open(connStr), &gorm.Config{})
	if err != nil {
		t.Fatalf("Failed to connect to database: %v", err)
	}

	// 3. Create trip_status enum type (required before AutoMigrate)
	_ = db.Exec("DROP TYPE IF EXISTS trip_status").Error
	err = db.Exec("CREATE TYPE trip_status AS ENUM ('PENDING', 'CONFIRMED', 'ACTIVE', 'COMPLETED', 'CANCELLED')").Error
	if err != nil {
		t.Fatalf("Failed to create trip_status enum: %v", err)
	}

	// 4. Auto-migrate schema (creates the trips table)
	err = db.AutoMigrate(&domain.Trip{})
	if err != nil {
		t.Fatalf("Failed to migrate database: %v", err)
	}

	// Return the DB instance and the cleanup function
	return db, func() {
		_ = pgContainer.Terminate(ctx)
	}
}

func TestTripRepository_FullCycle(t *testing.T) {
	db, cleanup := setupTestDB(t)
	defer cleanup()

	repo := NewTripRepository(db)
	ctx := context.Background()

	// Create a test trip object
	tripID := uuid.New()
	testTrip := &domain.Trip{
		ID:          tripID,
		PassengerID: uuid.New(),
		Pickup:      "123 Main St",
		Dropoff:     "456 Oak Ave",
		Status:      domain.TripStatusPending,
	}

	// Test 1: Creation (CREATE)
	t.Run("Create Trip", func(t *testing.T) {
		err := repo.Create(ctx, testTrip)
		assert.NoError(t, err)
	})

	// Test 2: Retrieval by ID (READ)
	t.Run("Get Trip By ID", func(t *testing.T) {
		found, err := repo.GetByID(ctx, tripID)
		assert.NoError(t, err)
		assert.NotNil(t, found)
		assert.Equal(t, tripID, found.ID)
	})

	// Test 3: Update (UPDATE)
	t.Run("Update Trip Status", func(t *testing.T) {
		testTrip.Status = domain.TripStatusActive
		driverID := uuid.New()
		testTrip.DriverID = &driverID

		err := repo.Update(ctx, testTrip)
		assert.NoError(t, err)

		found, _ := repo.GetByID(ctx, tripID)
		assert.Equal(t, domain.TripStatusActive, found.Status)
		assert.Equal(t, driverID, *found.DriverID)
	})

	// Test 4: Deletion (DELETE)
	t.Run("Delete Trip", func(t *testing.T) {
		err := repo.Delete(ctx, tripID)
		assert.NoError(t, err)

		// Verify that the record is truly deleted
		found, err := repo.GetByID(ctx, tripID)
		
		// FIX: Now we verify our domain error instead of a raw GORM string
		assert.ErrorIs(t, err, domain.ErrTripNotFound)
		assert.Nil(t, found)
	})
}
