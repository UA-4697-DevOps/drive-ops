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

	// [NEW] AWS SDK Imports
	"github.com/aws/aws-sdk-go-v2/config"

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
			time.Sleep(time.Duration(i+1) * time.Second)
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

	// 2. Load Broker Config
	brokerConfig, err := broker.LoadConfig()
	if err != nil {
		log.Fatalf("Failed to load broker config: %v", err)
	}

	// [FIXED] Create a custom HTTP client. 
	// The timeout must be greater than SQS WaitTimeSeconds (20s).
	customHttpClient := &http.Client{
		Timeout: 30 * time.Second,
	}

	// [NEW] Initialize AWS Config
	// Pass customHttpClient to avoid premature timeouts during Long Polling.
	awsCfg, err := config.LoadDefaultConfig(context.TODO(),
		config.WithRegion(brokerConfig.AWSRegion),
		config.WithHTTPClient(customHttpClient),
	)
	if err != nil {
		log.Fatalf("Failed to load AWS Config: %v", err)
	}

	// 3. Initialize RabbitMQ publisher (Keeping this for OUTBOUND events as per current scope)
	var publisher *broker.RabbitMQPublisher
	err = connectWithRetry("RabbitMQ Publisher", func() error {
		var err error
		publisher, err = broker.NewRabbitMQPublisher(brokerConfig)
		return err
	})
	if err != nil {
		log.Fatalf("Fatal: %v", err)
	}

	// 4. Dependency Injection: Repository -> Service -> Handler
	repo := repository.NewTripRepository(db)
	svc := service.NewTripService(repo, publisher)
	handler := api.NewTripHandler(svc)

	// [CHANGED] Initialize SQS Consumer (Replaces RabbitMQ Consumer)
	sqsConsumer := broker.NewSQSConsumer(awsCfg, brokerConfig.SQS_DRIVER_ASSIGNED_URL, svc, brokerConfig)

	// Create a cancellable context for consumer shutdown
	consumerCtx, consumerCancel := context.WithCancel(context.Background())
	// [NEW] Channel to propagate fatal consumer errors to the main goroutine
	consumerErrCh := make(chan error, 1)

	// [FIXED] Only start consumer in background if SQS URL is provided.
	// This prevents the service from crashing in integration tests where SQS is absent.
	if brokerConfig.SQS_DRIVER_ASSIGNED_URL != "" {
		go func() {
			if err := sqsConsumer.Start(consumerCtx); err != nil {
				// Only propagate error if it wasn't a requested shutdown
				if consumerCtx.Err() == nil {
					consumerErrCh <- err
				}
			}
		}()
		log.Printf("INFO: SQS Consumer initialized for queue: %s", brokerConfig.SQS_DRIVER_ASSIGNED_URL)
	} else {
		log.Println("WARNING: SQS_DRIVER_ASSIGNED_URL is empty. SQS Consumer skipped (normal for tests).")
	}

	// 5. Router setup
	r := chi.NewRouter()

	r.Get("/health", handler.HealthCheck)

	r.Route("/trips", func(r chi.Router) {
		r.Post("/", handler.CreateTrip)
		r.Get("/{id}", handler.GetTrip)
		r.Patch("/{id}/assign-driver", handler.AssignDriver)
	})

	// 6. Setup HTTP server with graceful shutdown
	serverPort := getEnv("TRIP_SERVICE_PORT", ":8081")
	srv := &http.Server{
		Addr:    serverPort,
		Handler: r,
	}

	stop := make(chan os.Signal, 1)
	signal.Notify(stop, os.Interrupt, syscall.SIGTERM)

	go func() {
		log.Printf("Trip Service is running on %s...", serverPort)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("Server failed: %v", err)
		}
	}()

	// [FIXED] Wait for either an OS interrupt or a fatal background error
	select {
	case sig := <-stop:
		log.Printf("Received signal %v, shutting down server...", sig)
	case err := <-consumerErrCh:
		log.Fatalf("CRITICAL: SQS Consumer failed: %v", err)
	}

	// 7. Graceful shutdown logic
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	// Stop HTTP Server
	if err := srv.Shutdown(ctx); err != nil {
		log.Printf("Server shutdown error: %v", err)
	}

	// [CHANGED] Stop SQS Consumer
	log.Println("Stopping SQS Consumer...")
	consumerCancel()
	// Optional: Add a small delay or WaitGroup if you need to ensure the poll loop exits strictly
	time.Sleep(500 * time.Millisecond)

	// Close publisher
	if err := publisher.Close(); err != nil {
		log.Printf("Error closing publisher: %v", err)
	}

	log.Println("Server stopped gracefully")
}
