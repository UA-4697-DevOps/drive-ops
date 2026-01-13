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

	"trip-service/internal/broker"
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
	// Simple wait for dependencies to spin up in docker-compose
	time.Sleep(5 * time.Second)

	if err := godotenv.Load(); err != nil {
		log.Println("Note: .env file not found, using system env variables")
	}

	// 1. Database Connection setup
	var dsn string
	if dbURL := os.Getenv("DB_URL"); dbURL != "" {
		dsn = dbURL
	} else {
		dsn = fmt.Sprintf("host=%s user=%s password=%s dbname=%s port=%s sslmode=disable",
			getEnv("DB_HOST", "localhost"),
			getEnv("DB_USER", "postgres"),
			getEnv("DB_PASSWORD", "postgres"),
			getEnv("TRIP_DB_NAME", "trip_db"),
			getEnv("DB_PORT", "5432"),
		)
	}

	db, err := gorm.Open(postgres.Open(dsn), &gorm.Config{})
	if err != nil {
		log.Fatalf("Failed to connect to database: %v", err)
	}

	// 2. Initialize RabbitMQ publisher (Keep from main)
	brokerConfig, err := broker.LoadConfig()
	if err != nil {
		log.Fatalf("Failed to load broker config: %v", err)
	}

	publisher, err := broker.NewRabbitMQPublisher(brokerConfig)
	if err != nil {
		log.Fatalf("Failed to connect to RabbitMQ: %v", err)
	}

	// 3. Dependency Injection: Repository -> Service -> Handler
	repo := repository.NewTripRepository(db)
	// Passing publisher to service as required for events (Phase 2 & 3)
	svc := service.NewTripService(repo, publisher)
	handler := api.NewTripHandler(svc)

	// Initialize RabbitMQ Consumer
	consumer, err := broker.NewRabbitMQConsumer(brokerConfig, svc)
	if err != nil {
		log.Fatalf("Failed to initialize RabbitMQ consumer: %v", err)
	}

	// Create a cancellable context for consumer
	consumerCtx, consumerCancel := context.WithCancel(context.Background())

	// Start consumer in background
	if err := consumer.Start(consumerCtx); err != nil {
		log.Fatalf("Failed to start consumer: %v", err)
	}

	// 4. Router setup
	r := chi.NewRouter()

	r.Get("/health", handler.HealthCheck)

	r.Route("/trips", func(r chi.Router) {
		r.Post("/", handler.CreateTrip)
		r.Get("/{id}", handler.GetTrip)

		// New endpoint for driver assignment (integrated from feature branch)
		r.Patch("/{id}/assign-driver", handler.AssignDriver)
	})

	// 5. Setup HTTP server with graceful shutdown (Preferred production way)
	serverPort := getEnv("TRIP_SERVICE_PORT", ":8081")
	srv := &http.Server{
		Addr:    serverPort,
		Handler: r,
	}

	// Channel to listen for interrupt signals
	stop := make(chan os.Signal, 1)
	signal.Notify(stop, os.Interrupt, syscall.SIGTERM)

	// Start server in a goroutine
	go func() {
		log.Printf("Trip Service is running on %s...", serverPort)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("Server failed: %v", err)
		}
	}()

	// Wait for interrupt signal
	<-stop
	log.Println("Shutting down server...")

	// 6. Graceful shutdown logic
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	if err := srv.Shutdown(ctx); err != nil {
		log.Printf("Server shutdown error: %v", err)
	}

	// Cancel consumer context to signal shutdown
	consumerCancel()

	if err := consumer.Close(); err != nil {
		log.Printf("Error closing consumer: %v", err)
	}

	// Close publisher last - both HTTP handlers and consumer may use it
	if err := publisher.Close(); err != nil {
		log.Printf("Error closing publisher: %v", err)
	}

	log.Println("Server stopped gracefully")
}
