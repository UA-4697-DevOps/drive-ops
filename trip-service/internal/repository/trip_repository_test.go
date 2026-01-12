//go:build integration
// +build integration

package repository

import (
	"context"
	"fmt"
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

// setupTestDB initializes a temporary Postgres container using t.Cleanup for reliability.
// It uses a build tag to prevent breaking non-Docker environments.
func setupTestDB(t *testing.T) *gorm.DB {
	// 1. Setup bounded context for container startup to avoid infinite hangs.
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()

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

	// 2. Register cleanup via t.Cleanup for robust resource management.
	t.Cleanup(func() {
		// Use a fresh background context to ensure termination completes.
		terminateCtx, terminateCancel := context.WithTimeout(context.Background(), 15*time.Second)
		defer terminateCancel()
		if err := pgContainer.Terminate(terminateCtx); err != nil {
			t.Errorf("Failed to terminate container: %v", err)
		}
	})

	connStr, err := pgContainer.ConnectionString(ctx, "sslmode=disable")
	if err != nil {
		t.Fatalf("Failed to get connection string: %v", err)
	}

	// 3. Connect GORM and apply schema
	db, err := gorm.Open(gormPostgres.Open(connStr), &gorm.Config{})
	if err != nil {
		t.Fatalf("Failed to connect to database: %v", err)
	}

	// Dynamic Enum Creation to prevent drift from domain constants.
	if err := setupEnums(db); err != nil {
		t.Fatalf("Failed to setup enums: %v", err)
	}

	if err := db.AutoMigrate(&domain.Trip{}); err != nil {
		t.Fatalf("Failed to migrate database: %v", err)
	}

	return db
}

// setupEnums centralizes DDL logic to stay in sync with domain constants.
func setupEnums(db *gorm.DB) error {
	_ = db.Exec("DROP TYPE IF EXISTS trip_status").Error
	enumSQL := fmt.Sprintf("CREATE TYPE trip_status AS ENUM ('%s', '%s', '%s', '%s', '%s')",
		domain.TripStatusPending,
		domain.TripStatusConfirmed,
		domain.TripStatusActive,
		domain.TripStatusCompleted,
		domain.TripStatusCancelled,
	)
	return db.Exec(enumSQL).Error
}

func TestTripRepository_FullCycle(t *testing.T) {
	db := setupTestDB(t)
	repo := NewTripRepository(db)
	ctx := context.Background()

	tripID := uuid.New()
	testTrip := &domain.Trip{
		ID:          tripID,
		PassengerID: uuid.New(),
		Pickup:      "123 Main St", // Required NOT NULL field
		Dropoff:     "456 Oak Ave", // Required NOT NULL field
		Status:      domain.TripStatusPending,
	}

	t.Run("Create Trip", func(t *testing.T) {
		err := repo.Create(ctx, testTrip)
		assert.NoError(t, err, "Seeding test trip must not fail")
	})

	t.Run("Update Trip Status", func(t *testing.T) {
		testTrip.Status = domain.TripStatusActive
		driverID := uuid.New()
		testTrip.DriverID = &driverID

		err := repo.Update(ctx, testTrip)
		assert.NoError(t, err)

		// Verify result while checking for errors to avoid misleading failures.
		found, err := repo.GetByID(ctx, tripID)
		assert.NoError(t, err)
		assert.Equal(t, domain.TripStatusActive, found.Status)
	})
}

func TestTripRepository_AssignDriver(t *testing.T) {
	db := setupTestDB(t)
	repo := NewTripRepository(db)
	ctx := context.Background()

	// Subtests now seed their own data to ensure isolation.
	t.Run("Success Assignment", func(t *testing.T) {
		tripID := uuid.New()
		trip := &domain.Trip{
			ID:          tripID,
			PassengerID: uuid.New(),
			Pickup:      "Station A", // Required field
			Dropoff:     "Station B", // Required field
			Status:      domain.TripStatusPending,
		}
		assert.NoError(t, repo.Create(ctx, trip))

		driverID := uuid.New()
		err := repo.AssignDriver(ctx, tripID, driverID)
		assert.NoError(t, err)
		
		found, err := repo.GetByID(ctx, tripID)
		assert.NoError(t, err, "Error from GetByID must be handled")
		assert.Equal(t, domain.TripStatusConfirmed, found.Status)
	})

	t.Run("Conflict - Already Assigned", func(t *testing.T) {
		tripID := uuid.New()
		trip := &domain.Trip{
			ID:          tripID,
			PassengerID: uuid.New(),
			Pickup:      "Point C",
			Dropoff:     "Point D",
			Status:      domain.TripStatusConfirmed,
			DriverID:    &[]uuid.UUID{uuid.New()}[0],
		}
		assert.NoError(t, repo.Create(ctx, trip))

		err := repo.AssignDriver(ctx, tripID, uuid.New())
		assert.ErrorIs(t, err, domain.ErrInvalidTripStatus)
	})
}
