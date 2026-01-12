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

	// 1. Setup and start the Postgres container
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

	connStr, err := pgContainer.ConnectionString(ctx, "sslmode=disable")
	if err != nil {
		t.Fatalf("Failed to get connection string: %v", err)
	}

	// 2. Connect GORM to the container instance
	db, err := gorm.Open(gormPostgres.Open(connStr), &gorm.Config{})
	if err != nil {
		t.Fatalf("Failed to connect to database: %v", err)
	}

	// 3. Create trip_status enum type
	_ = db.Exec("DROP TYPE IF EXISTS trip_status").Error
	err = db.Exec("CREATE TYPE trip_status AS ENUM ('PENDING', 'CONFIRMED', 'ACTIVE', 'COMPLETED', 'CANCELLED')").Error
	if err != nil {
		t.Fatalf("Failed to create trip_status enum: %v", err)
	}

	// 4. Auto-migrate schema
	err = db.AutoMigrate(&domain.Trip{})
	if err != nil {
		t.Fatalf("Failed to migrate database: %v", err)
	}

	return db, func() {
		// Use Background context to ensure termination completes
		_ = pgContainer.Terminate(context.Background())
	}
}

// TestTripRepository_FullCycle tests basic CRUD operations
func TestTripRepository_FullCycle(t *testing.T) {
	db, cleanup := setupTestDB(t)
	defer cleanup()

	repo := NewTripRepository(db)
	ctx := context.Background()

	tripID := uuid.New()
	testTrip := &domain.Trip{
		ID:          tripID,
		PassengerID: uuid.New(),
		Pickup:      "123 Main St",
		Dropoff:     "456 Oak Ave",
		Status:      domain.TripStatusPending,
	}

	t.Run("Create Trip", func(t *testing.T) {
		err := repo.Create(ctx, testTrip)
		assert.NoError(t, err)
	})

	t.Run("Get Trip By ID", func(t *testing.T) {
		found, err := repo.GetByID(ctx, tripID)
		assert.NoError(t, err)
		assert.NotNil(t, found)
		assert.Equal(t, tripID, found.ID)
	})

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

	t.Run("Delete Trip", func(t *testing.T) {
		err := repo.Delete(ctx, tripID)
		assert.NoError(t, err)

		found, err := repo.GetByID(ctx, tripID)
		assert.ErrorIs(t, err, domain.ErrTripNotFound)
		assert.Nil(t, found)
	})
}

// TestTripRepository_AssignDriver tests the atomic driver assignment logic
func TestTripRepository_AssignDriver(t *testing.T) {
	db, cleanup := setupTestDB(t)
	defer cleanup()

	repo := NewTripRepository(db)
	ctx := context.Background()

	// 1. Seed a PENDING trip
	tripID := uuid.New()
	testTrip := &domain.Trip{
		ID:          tripID,
		PassengerID: uuid.New(),
		Pickup:      "Start Point",
		Dropoff:     "End Point",
		Status:      domain.TripStatusPending,
	}
	
	// FIXED: Verify that seeding succeeded to avoid misleading failures later
	err := repo.Create(ctx, testTrip)
	assert.NoError(t, err, "Seeding test trip must not fail")

	t.Run("Success Assignment", func(t *testing.T) {
		driverID := uuid.New()
		err := repo.AssignDriver(ctx, tripID, driverID)
		
		assert.NoError(t, err)
		
		found, _ := repo.GetByID(ctx, tripID)
		assert.Equal(t, domain.TripStatusConfirmed, found.Status)
		assert.NotNil(t, found.DriverID)
		assert.Equal(t, driverID, *found.DriverID)
	})

	t.Run("Conflict - Already Assigned", func(t *testing.T) {
		newDriverID := uuid.New()
		err := repo.AssignDriver(ctx, tripID, newDriverID)
		assert.ErrorIs(t, err, domain.ErrInvalidTripStatus)
	})

	t.Run("Trip Not Found", func(t *testing.T) {
		nonExistentID := uuid.New()
		err := repo.AssignDriver(ctx, nonExistentID, uuid.New())
		assert.ErrorIs(t, err, domain.ErrTripNotFound)
	})
}
