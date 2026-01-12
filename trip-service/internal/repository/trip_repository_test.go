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
	"github.com/testcontainers/testcontainers-go"
	"github.com/testcontainers/testcontainers-go/modules/postgres"
	"github.com/testcontainers/testcontainers-go/wait"
	gormPostgres "gorm.io/driver/postgres"
	"gorm.io/gorm"
)

// setupTestDB initializes a temporary Postgres container using t.Cleanup for reliability
func setupTestDB(t *testing.T) *gorm.DB {
	// Use a bounded context for container startup to avoid infinite hangs in CI
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

	// Register cleanup via t.Cleanup to ensure container is terminated 
	// even if the test panics or times out
	t.Cleanup(func() {
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

	db, err := gorm.Open(gormPostgres.Open(connStr), &gorm.Config{})
	if err != nil {
		t.Fatalf("Failed to connect to database: %v", err)
	}

	// Dynamic Enum Creation: Stays in sync with domain constants automatically
	err = setupEnums(db)
	if err != nil {
		t.Fatalf("Failed to setup enums: %v", err)
	}

	err = db.AutoMigrate(&domain.Trip{})
	if err != nil {
		t.Fatalf("Failed to migrate database: %v", err)
	}

	return db
}

// setupEnums centralizes DDL to prevent drift from domain logic
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

		found, err := repo.GetByID(ctx, tripID)
		assert.NoError(t, err)
		assert.Equal(t, domain.TripStatusActive, found.Status)
		assert.Equal(t, driverID, *found.DriverID)
	})
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
			Status:      domain.TripStatusPending,
		}
		assert.NoError(t, repo.Create(ctx, trip))

		driverID := uuid.New()
		err := repo.AssignDriver(ctx, tripID, driverID)
		assert.NoError(t, err)
		
		found, err := repo.GetByID(ctx, tripID)
		assert.NoError(t, err)
		assert.Equal(t, domain.TripStatusConfirmed, found.Status)
		assert.Equal(t, driverID, *found.DriverID)
	})

	t.Run("Conflict - Already Assigned", func(t *testing.T) {
		tripID := uuid.New()
		trip := &domain.Trip{
			ID:          tripID,
			PassengerID: uuid.New(),
			Status:      domain.TripStatusConfirmed,
			DriverID:    &[]uuid.UUID{uuid.New()}[0],
		}
		assert.NoError(t, repo.Create(ctx, trip))

		err := repo.AssignDriver(ctx, tripID, uuid.New())
		assert.ErrorIs(t, err, domain.ErrInvalidTripStatus)
	})
}
