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

// Update performs a generic update of the trip record
func (r *TripRepository) Update(ctx context.Context, trip *domain.Trip) error {
	return r.db.WithContext(ctx).Save(trip).Error
}

// AssignDriver atomically assigns a driver and updates status to CONFIRMED.
// It differentiates between "Trip Not Found" and "Invalid Status" errors.
func (r *TripRepository) AssignDriver(ctx context.Context, tripID uuid.UUID, driverID uuid.UUID) error {
	// 43-57: Attempt atomic update with a guard on status and unassigned status (driver_id IS NULL).
	// This prevents concurrent drivers from accepting the same trip.
	result := r.db.WithContext(ctx).
		Model(&domain.Trip{}).
		Where("id = ? AND status = ? AND driver_id IS NULL", tripID, domain.TripStatusPending).
		Updates(map[string]interface{}{
			"driver_id": driverID,
			"status":    domain.TripStatusConfirmed,
		})

	if result.Error != nil {
		return result.Error
	}

	// If no rows were updated, we need to determine the cause (404 vs 409)
	if result.RowsAffected == 0 {
		var count int64
		// Robust and DB-agnostic existence check using Count()
		err := r.db.WithContext(ctx).
			Model(&domain.Trip{}).
			Where("id = ?", tripID).
			Count(&count).
			Error

		if err != nil {
			return err
		}

		if count == 0 {
			// Trip ID truly does not exist
			return domain.ErrTripNotFound
		}

		// Trip exists but is not PENDING or already has a driver assigned
		return domain.ErrInvalidTripStatus
	}

	return nil
}

// Delete removes a trip record by its id
func (r *TripRepository) Delete(ctx context.Context, id uuid.UUID) error {
	return r.db.WithContext(ctx).Delete(&domain.Trip{}, "id = ?", id).Error
}

// DB returns the underlying database connection for health checks
func (r *TripRepository) DB() *gorm.DB {
	return r.db
}
