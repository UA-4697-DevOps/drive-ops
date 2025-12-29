package main

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"trip-service/internal/domain"
	"trip-service/internal/service"

	api "trip-service/internal/api/http"

	"github.com/go-chi/chi/middleware"
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

	dsn := fmt.Sprintf("host=%s user=%s password=%s dbname=%s port=%s sslmode=%s",
		getEnv("DB_HOST", "localhost"),
		getEnv("DB_USER", "postgres"),
		getEnv("DB_PASSWORD", "postgres"),
		getEnv("DB_NAME", "trip_db"),
		getEnv("DB_PORT", "5432"),
		getEnv("DB_SSLMODE", "disable"),
	)

	db, err := gorm.Open(postgres.Open(dsn), &gorm.Config{})
	if err != nil {
		log.Fatalf("Failed to connect to database: %v", err)
	}

	if err := db.AutoMigrate(&domain.Trip{}); err != nil {
		log.Fatalf("Failed to migrate database: %v", err)
	}

	//Dependency Injection
	// repo := repository.NewTripRepository(db)
	svc := &service.MockTripService{}
	handler := api.NewTripHandler(svc)

	r := chi.NewRouter()

	r.Use(middleware.Logger)
	r.Use(middleware.Recoverer)
	r.Use(middleware.RequestID)
	r.Use(middleware.Timeout(60 * time.Second))

	r.Get("/health", handler.HealthCheck)
	r.Route("/trips", func(r chi.Router) {
		r.Post("/", handler.CreateTrip)
		r.Get("/{id}", handler.GetTrip)
	})

	log.Printf("Server is running on %s...", getEnv("SERVER_PORT", ":8080"))
	srv := &http.Server{
		Addr:    getEnv("SERVER_PORT", ":8080"),
		Handler: r,
	}

	// Start server in goroutine
	go func() {
		log.Printf("Server is running on %s...", srv.Addr)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("Server failed: %v", err)
		}
	}()

	// Wait for interrupt signal
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	log.Println("Shutting down server...")
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	if err := srv.Shutdown(ctx); err != nil {
		log.Fatalf("Server forced to shutdown: %v", err)
	}
	log.Println("Server exited")
}
