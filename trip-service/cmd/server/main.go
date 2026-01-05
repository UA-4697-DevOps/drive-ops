package main

import (
	"fmt"
	"log"
	"net/http"
	"os"

	"trip-service/internal/repository"
	"trip-service/internal/service"

	api "trip-service/internal/api/http"

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

	// Database Connection setup
	var dsn string
	if dbURL := os.Getenv("DB_URL"); dbURL != "" {
		dsn = dbURL
	} else {
		dsn = fmt.Sprintf("host=%s user=%s password=%s dbname=%s port=%s sslmode=disable",
			getEnv("DB_HOST", "localhost"),
			getEnv("DB_USER", "postgres"),
			getEnv("DB_PASSWORD", "postgres"),
			getEnv("DB_NAME", "trip_db"),
			getEnv("DB_PORT", "5432"),
		)
	}

	db, err := gorm.Open(postgres.Open(dsn), &gorm.Config{})
	if err != nil {
		log.Fatalf("Failed to connect to database: %v", err)
	}

	// Dependency Injection: Repository -> Service -> Handler
	repo := repository.NewTripRepository(db)
	svc := service.NewTripService(repo)
	handler := api.NewTripHandler(svc)

	r := chi.NewRouter()

	// Routes
	r.Get("/health", handler.HealthCheck)
	
	r.Route("/trips", func(r chi.Router) {
		r.Post("/", handler.CreateTrip)
		r.Get("/{id}", handler.GetTrip)
		
		// New endpoint for driver assignment (Task requirement)
		r.Patch("/{id}/assign-driver", handler.AssignDriver)
	})

	serverPort := getEnv("SERVER_PORT", ":8080")
	log.Printf("Trip Service is running on %s...", serverPort)
	log.Fatal(http.ListenAndServe(serverPort, r))
}
