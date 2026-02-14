package repository

import (
	"context"
	"errors"
	"trip-service/internal/domain"

	"github.com/google/uuid"
	"gorm.io/gorm"
)

type TripRepository struct {
	db *gorm.DB
}

func NewTripRepository(db *gorm.DB) *TripRepository {
	return &TripRepository{db: db}
}

// WithTransaction executes the provided function within a database transaction.
// It ensures that all operations in the callback are committed atomically,
// or rolled back if any error is returned.
func (r *TripRepository) WithTransaction(ctx context.Context, fn func(txRepo *TripRepository) error) error {
	return r.db.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		txRepo := &TripRepository{db: tx}
		return fn(txRepo)
	})
}

// Create persists a new trip record into the database
func (r *TripRepository) Create(ctx context.Context, trip *domain.Trip) error {
	return r.db.WithContext(ctx).Create(trip).Error
}

// GetByID retrieves a trip by its unique identifier
func (r *TripRepository) GetByID(ctx context.Context, id uuid.UUID) (*domain.Trip, error) {
	var trip domain.Trip
	err := r.db.WithContext(ctx).First(&trip, "id = ?", id).Error
	if err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			return nil, domain.ErrTripNotFound
		}
		return nil, err
	}
	return &trip, nil
}

// Update performs a generic update of the trip record.
// Used for general metadata updates.
func (r *TripRepository) Update(ctx context.Context, trip *domain.Trip) error {
	return r.db.WithContext(ctx).Save(trip).Error
}

// AssignDriver atomically assigns a driver and updates status to ACTIVE.
// It prevents race conditions using atomic SQL updates.
func (r *TripRepository) AssignDriver(ctx context.Context, tripID uuid.UUID, driverID uuid.UUID) error {
	// Atomic update with guard: only update if trip is PENDING and has no driver
	result := r.db.WithContext(ctx).
		Model(&domain.Trip{}).
		Where("id = ? AND status = ? AND driver_id IS NULL", tripID, domain.TripStatusPending).
		Updates(map[string]interface{}{
			"driver_id": driverID,
			"status":    domain.TripStatusActive,
		})

	if result.Error != nil {
		return result.Error
	}

	// If no rows were affected, differentiate between 404 (Not Found) and 409 (Conflict)
	if result.RowsAffected == 0 {
		return r.checkUpdateFailure(ctx, tripID)
	}

	return nil
}

// CompleteTrip atomically marks a trip as COMPLETED.
// It ensures that only ACTIVE trips can be completed.
func (r *TripRepository) CompleteTrip(ctx context.Context, tripID uuid.UUID) error {
	// Atomic update with guard: only update if trip is currently ACTIVE
	result := r.db.WithContext(ctx).
		Model(&domain.Trip{}).
		Where("id = ? AND status = ?", tripID, domain.TripStatusActive).
		Update("status", domain.TripStatusCompleted)

	if result.Error != nil {
		return result.Error
	}

	// Handle idempotency: if no rows were affected, check why
	if result.RowsAffected == 0 {
		return r.checkUpdateFailure(ctx, tripID)
	}

	return nil
}

// checkUpdateFailure is a helper to distinguish between a missing trip and an invalid state
func (r *TripRepository) checkUpdateFailure(ctx context.Context, id uuid.UUID) error {
	var count int64
	err := r.db.WithContext(ctx).
		Model(&domain.Trip{}).
		Where("id = ?", id).
		Count(&count).
		Error

	if err != nil {
		return err
	}

	if count == 0 {
		return domain.ErrTripNotFound
	}

	return domain.ErrInvalidTripStatus
}

// Delete removes a trip record by its id
func (r *TripRepository) Delete(ctx context.Context, id uuid.UUID) error {
	return r.db.WithContext(ctx).Delete(&domain.Trip{}, "id = ?", id).Error
}

// Ping verifies the database connection status.
func (r *TripRepository) Ping(ctx context.Context) error {
	sqlDB, err := r.db.DB()
	if err != nil {
		return err
	}
	return sqlDB.PingContext(ctx)
}
