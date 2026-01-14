//go:build integration

package repository

import (
	"context"
	"fmt"
	"testing"
	"time"

	"trip-service/internal/domain"

	"github.com/google/uuid"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"github.com/testcontainers/testcontainers-go"
	"github.com/testcontainers/testcontainers-go/modules/postgres"
	"github.com/testcontainers/testcontainers-go/wait"
	gormPostgres "gorm.io/driver/postgres"
	"gorm.io/gorm"
)

// setupTestDB initializes a temporary Postgres container with robust cleanup logic.
func setupTestDB(t *testing.T) *gorm.DB {
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()

	// 1. Start the container
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

	// 2. Connect GORM
	connStr, err := pgContainer.ConnectionString(ctx, "sslmode=disable")
	if err != nil {
		t.Fatalf("Failed to get connection string: %v", err)
	}

	db, err := gorm.Open(gormPostgres.Open(connStr), &gorm.Config{})
	if err != nil {
		t.Fatalf("Failed to connect to database: %v", err)
	}

	// 3. Register comprehensive cleanup
	t.Cleanup(func() {
		// Explicitly close the DB connection pool
		if sqlDB, err := db.DB(); err == nil {
			_ = sqlDB.Close()
		}

		// Terminate the container
		terminateCtx, terminateCancel := context.WithTimeout(context.Background(), 15*time.Second)
		defer terminateCancel()
		_ = pgContainer.Terminate(terminateCtx)
	})

	if err := setupEnums(db); err != nil {
		t.Fatalf("Failed to setup enums: %v", err)
	}

	if err := db.AutoMigrate(&domain.Trip{}); err != nil {
		t.Fatalf("Failed to migrate database: %v", err)
	}

	return db
}

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

func TestTripRepository_AssignDriver(t *testing.T) {
	db := setupTestDB(t)
	repo := NewTripRepository(db)
	ctx := context.Background()

	t.Run("Success Assignment", func(t *testing.T) {
		tripID := uuid.New()
		trip := &domain.Trip{
			ID:          tripID,
			PassengerID: uuid.New(),
			Pickup:      "Station A",
			Dropoff:     "Station B",
			Status:      domain.TripStatusPending,
		}
		require.NoError(t, repo.Create(ctx, trip))

		driverID := uuid.New()
		err := repo.AssignDriver(ctx, tripID, driverID)
		assert.NoError(t, err)
		
		found, err := repo.GetByID(ctx, tripID)
		assert.NoError(t, err)
		
		// FIXED: Nil guard before dereferencing DriverID to prevent test panic
		require.NotNil(t, found.DriverID, "DriverID should not be nil after assignment")
		assert.Equal(t, domain.TripStatusConfirmed, found.Status)
		assert.Equal(t, driverID, *found.DriverID)
	})

	t.Run("Conflict - Already Assigned", func(t *testing.T) {
		tripID := uuid.New()
		existingDriverID := uuid.New()
		trip := &domain.Trip{
			ID:          tripID,
			PassengerID: uuid.New(),
			Pickup:      "Point C",
			Dropoff:     "Point D",
			Status:      domain.TripStatusConfirmed,
			DriverID:    &existingDriverID,
		}
		require.NoError(t, repo.Create(ctx, trip))

		err := repo.AssignDriver(ctx, tripID, uuid.New())
		assert.ErrorIs(t, err, domain.ErrInvalidTripStatus)
	})

	t.Run("Trip Not Found", func(t *testing.T) {
		nonExistentID := uuid.New()
		err := repo.AssignDriver(ctx, nonExistentID, uuid.New())
		assert.ErrorIs(t, err, domain.ErrTripNotFound)
	})
}
