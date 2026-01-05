package repository

import (
	"context"
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

// CREATE: create new trip
func (r *TripRepository) Create(ctx context.Context, trip *domain.Trip) error {
	return r.db.WithContext(ctx).Create(trip).Error
}

// READ: get trip by id
func (r *TripRepository) GetByID(ctx context.Context, id uuid.UUID) (*domain.Trip, error) {
	var trip domain.Trip
	err := r.db.WithContext(ctx).First(&trip, "id = ?", id).Error
	if err != nil {
		if err == gorm.ErrRecordNotFound {
			return nil, domain.ErrTripNotFound
		}
		return nil, err
	}
	return &trip, nil
}

// UPDATE: update trip status (generic update)
func (r *TripRepository) Update(ctx context.Context, trip *domain.Trip) error {
	return r.db.WithContext(ctx).Save(trip).Error
}

// ASSIGN: Atomically assign a driver and update status to CONFIRMED
// This method ensures we only update trips that are currently PENDING
func (r *TripRepository) AssignDriver(ctx context.Context, tripID uuid.UUID, driverID uuid.UUID) error {
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

	if result.RowsAffected == 0 {
		// Either the trip doesn't exist or it's no longer PENDING
		return domain.ErrInvalidTripStatus
	}

	return nil
}

// DELETE: delete trip by id
func (r *TripRepository) Delete(ctx context.Context, id uuid.UUID) error {
	return r.db.WithContext(ctx).Delete(&domain.Trip{}, "id = ?", id).Error
}

// DB returns the underlying database connection for health checks
func (r *TripRepository) DB() *gorm.DB {
	return r.db
}
