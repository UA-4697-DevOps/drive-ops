package repository

import (
	"context"
	"errors" // Added for proper error checking
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
		// FIX: Use errors.Is to correctly identify wrapped GORM errors
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
	// Attempt atomic update
	result := r.db.WithContext(ctx).
		Model(&domain.Trip{}).
		Where("id = ? AND status = ?", tripID, domain.TripStatusPending).
		Updates(map[string]interface{}{
			"driver_id": driverID,
			"status":    domain.TripStatusConfirmed,
		})

	if result.Error != nil {
		return result.Error
	}

	// If no rows were updated, we need to find out why
	if result.RowsAffected == 0 {
		var exists bool
		err := r.db.WithContext(ctx).
			Model(&domain.Trip{}).
			Select("count(*) > 0").
			Where("id = ?", tripID).
			Find(&exists).
			Error

		if err != nil {
			return err
		}

		if !exists {
			// Trip ID truly does not exist in the database
			return domain.ErrTripNotFound
		}

		// Trip exists, but its status was not PENDING (already taken or cancelled)
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
