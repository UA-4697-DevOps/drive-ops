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
		return nil, err
	}
	return &trip, nil
}

// UPDATE: update trip status(driver id for example)
func (r *TripRepository) Update(ctx context.Context, trip *domain.Trip) error {
	return r.db.WithContext(ctx).Save(trip).Error
}

// DELETE: delete trip by id
func (r *TripRepository) Delete(ctx context.Context, id uuid.UUID) error {
	return r.db.WithContext(ctx).Delete(&domain.Trip{}, "id = ?", id).Error
}

