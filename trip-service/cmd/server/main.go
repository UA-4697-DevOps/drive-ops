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
	if err := godotenv.Load(); err != nil {
		log.Println("Note: .env file not found, using system env variables")
	}

	// Helper for retry logic
	connectWithRetry := func(desc string, fn func() error) error {
		var err error
		for i := 0; i < 10; i++ {
			if err = fn(); err == nil {
				log.Printf("Successfully connected to %s", desc)
				return nil
			}
			log.Printf("Failed to connect to %s (attempt %d/10): %v", desc, i+1, err)
			time.Sleep(time.Duration(i+1) * time.Second) // Exponential backoff: 1s, 2s, 3s... (actually linear here but sufficient)
		}
		return fmt.Errorf("failed to connect to %s after retries: %w", desc, err)
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

	var db *gorm.DB
	err := connectWithRetry("Postgres", func() error {
		var err error
		db, err = gorm.Open(postgres.Open(dsn), &gorm.Config{})
		return err
	})
	if err != nil {
		log.Fatalf("Fatal: %v", err)
	}

	// 2. Initialize RabbitMQ publisher
	brokerConfig, err := broker.LoadConfig()
	if err != nil {
		log.Fatalf("Failed to load broker config: %v", err)
	}

	var publisher *broker.RabbitMQPublisher
	err = connectWithRetry("RabbitMQ Publisher", func() error {
		var err error
		publisher, err = broker.NewRabbitMQPublisher(brokerConfig)
		return err
	})
	if err != nil {
		log.Fatalf("Fatal: %v", err)
	}

	// 3. Dependency Injection: Repository -> Service -> Handler
	repo := repository.NewTripRepository(db)
	svc := service.NewTripService(repo, publisher)
	handler := api.NewTripHandler(svc)

	// Initialize RabbitMQ Consumer
	var consumer *broker.RabbitMQConsumer
	err = connectWithRetry("RabbitMQ Consumer", func() error {
		var err error
		consumer, err = broker.NewRabbitMQConsumer(brokerConfig, svc)
		return err
	})
	if err != nil {
		log.Fatalf("Fatal: %v", err)
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

	// Give consumer time to finish in-flight messages
	consumerShutdownDone := make(chan struct{})
	go func() {
		if err := consumer.Close(); err != nil {
			log.Printf("Error closing consumer: %v", err)
		}
		close(consumerShutdownDone)
	}()

	select {
	case <-consumerShutdownDone:
		log.Println("Consumer closed gracefully")
	case <-time.After(10 * time.Second):
		log.Println("Consumer close timed out")
	}

	// Close publisher last - both HTTP handlers and consumer may use it
	if err := publisher.Close(); err != nil {
		log.Printf("Error closing publisher: %v", err)
	}

	log.Println("Server stopped gracefully")
}
