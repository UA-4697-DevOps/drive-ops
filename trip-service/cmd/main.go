package main

import (
	"fmt"
	"log"
	"net/http"
	"os"

	"github.com/UA-4697-DevOps/drive-ops/trip-service/internal/repository"
	"github.com/UA-4697-DevOps/drive-ops/trip-service/internal/service"

	api "github.com/UA-4697-DevOps/drive-ops/trip-service/internal/api/http"

	"github.com/go-chi/chi/v5"
	"github.com/joho/godotenv"
	"gorm.io/driver/postgres"
	"gorm.io/gorm"
)

func getEnv(key, fallback string) string {
	if value, ok := os.LookupEnv(key); ok {
		return value
	}
	return fallback
}

func main() {
	if err := godotenv.Load(); err != nil {
		log.Println("Note: .env file not found, using system env variables")
	}

	dsn := fmt.Sprintf("host=%s user=%s password=%s dbname=%s port=%s sslmode=disable",
		getEnv("DB_HOST", "localhost"),
		getEnv("DB_USER", "postgres"),
		getEnv("DB_PASSWORD", "postgres"),
		getEnv("DB_NAME", "trip_db"),
		getEnv("DB_PORT", "5432"),
	)

	db, err := gorm.Open(postgres.Open(dsn), &gorm.Config{})
	if err != nil {
		log.Fatalf("Failed to connect to database: %v", err)
	}

	//Dependency Injection
	repo := repository.NewTripRepository(db)
	svc := service.NewTripService(repo)
	handler := api.NewTripHandler(svc)

	r := chi.NewRouter()

	r.Get("/health", handler.HealthCheck)
	r.Route("/trips", func(r chi.Router) {
		r.Post("/", handler.CreateTrip)
		r.Get("/{id}", handler.GetTrip)
	})

	log.Printf("Server is running on %s...", getEnv("SERVER_PORT", ":8080"))
	log.Fatal(http.ListenAndServe(getEnv("SERVER_PORT", ":8080"), r))
}
