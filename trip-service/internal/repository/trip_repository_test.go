package repository

import (
	"context"
	"testing"
	"time"

	"github.com/UA-4697-DevOps/drive-ops/trip-service/internal/domain"
	"github.com/google/uuid"
	"github.com/stretchr/testify/assert"
	"github.com/testcontainers/testcontainers-go"
	"github.com/testcontainers/testcontainers-go/modules/postgres"
	"github.com/testcontainers/testcontainers-go/wait"
	gormPostgres "gorm.io/driver/postgres"
	"gorm.io/gorm"
)

// setupTestDB ініціалізує тимчасовий контейнер Postgres для тестів
func setupTestDB(t *testing.T) (*gorm.DB, func()) {
	ctx := context.Background()

	// 1. Налаштування та запуск контейнера Postgres (використовуємо 15-alpine для швидкості)
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

	// Отримання Connection String
	connStr, err := pgContainer.ConnectionString(ctx, "sslmode=disable")
	if err != nil {
		t.Fatalf("Failed to get connection string: %v", err)
	}

	// 2. Підключення GORM до контейнера
	db, err := gorm.Open(gormPostgres.Open(connStr), &gorm.Config{})
	if err != nil {
		t.Fatalf("Failed to connect to database: %v", err)
	}

	// 3. Авто-міграція схеми (створення таблиці trips)
	err = db.AutoMigrate(&domain.Trip{})
	if err != nil {
		t.Fatalf("Failed to migrate database: %v", err)
	}

	// Повертаємо об'єкт БД та функцію очищення
	return db, func() {
		_ = pgContainer.Terminate(ctx)
	}
}

func TestTripRepository_FullCycle(t *testing.T) {
	db, cleanup := setupTestDB(t)
	defer cleanup()

	repo := NewTripRepository(db)
	ctx := context.Background()

	// Створюємо тестову поїздку
	tripID := uuid.New()
	testTrip := &domain.Trip{
		ID:          tripID,
		PassengerID: uuid.New(),
		Status:      "PENDING",
	}

	// Тест 1: Створення (CREATE)
	t.Run("Create Trip", func(t *testing.T) {
		err := repo.Create(ctx, testTrip)
		assert.NoError(t, err)
	})

	// Тест 2: Отримання за ID (READ)
	t.Run("Get Trip By ID", func(t *testing.T) {
		found, err := repo.GetByID(ctx, tripID)
		assert.NoError(t, err)
		assert.NotNil(t, found)
		assert.Equal(t, tripID, found.ID)
		assert.Equal(t, "PENDING", found.Status)
	})

	// Тест 3: Оновлення (UPDATE)
	t.Run("Update Trip Status", func(t *testing.T) {
		testTrip.Status = "ACTIVE"
		driverID := uuid.New()
		testTrip.DriverID = &driverID

		err := repo.Update(ctx, testTrip)
		assert.NoError(t, err)

		found, _ := repo.GetByID(ctx, tripID)
		assert.Equal(t, "ACTIVE", found.Status)
		assert.Equal(t, driverID, *found.DriverID)
	})

	// Тест 4: Видалення (DELETE)
	t.Run("Delete Trip", func(t *testing.T) {
		err := repo.Delete(ctx, tripID)
		assert.NoError(t, err)

		// Перевіряємо, що запис дійсно видалено
		found, err := repo.GetByID(ctx, tripID)
		assert.Error(t, err)
		assert.Nil(t, found)
		assert.Contains(t, err.Error(), "record not found")
	})
}
