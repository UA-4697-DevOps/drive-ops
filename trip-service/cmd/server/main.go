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

	// [FIXED] Define a background context to manage the entire application lifecycle
	appCtx, appCancel := context.WithCancel(context.Background())
	defer appCancel()

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

	// [FIXED] Custom HTTP client for Long Polling (Timeout > 20s)
	// This is critical for SQS WaitTimeSeconds=20
	customHttpClient := &http.Client{
		Timeout: 30 * time.Second,
	}

	// 3. Initialize AWS Config (Using the appCtx)
	awsCfg, err := config.LoadDefaultConfig(appCtx,
		config.WithRegion(brokerConfig.AWSRegion),
		config.WithHTTPClient(customHttpClient),
	)
	if err != nil {
		log.Fatalf("Failed to load AWS Config: %v", err)
	}

	// 4. Initialize Outbound Publisher (SQS)
	if brokerConfig.SQS_TRIP_CREATED_URL == "" {
		log.Fatalf("Fatal: SQS_TRIP_CREATED_URL is not set in environment")
	}
	
	// [FIXED] Passing the AWS Config object to the New Publisher
	publisher := broker.NewSQSPublisher(awsCfg, brokerConfig.SQS_TRIP_CREATED_URL)
	log.Printf("Successfully initialized SQS Publisher on: %s", brokerConfig.SQS_TRIP_CREATED_URL)

	// 5. Dependency Injection
	repo := repository.NewTripRepository(db)
	svc := service.NewTripService(repo, publisher)
	handler := api.NewTripHandler(svc)

	// --- SQS Consumer Setup ---
    // [FIXED] Use the appCtx created at the start for unified cancellation
    consumerErrCh := make(chan error, 2)

    // Helper to start consumers in the background
    startConsumer := func(name string, url string) {
        if url == "" {
            log.Printf("WARNING: %s URL is empty. Consumer skipped.", name)
            return
        }
        
        // [FIXED] Using the simplified constructor from our refactored sqs_consumer.go
        consumer := broker.NewSQSConsumer(awsCfg, url, svc)
        go func() {
            log.Printf("INFO: Starting %s SQS Consumer on: %s", name, url)
            // Passes appCtx so polling stops when appCancel() is called
            if err := consumer.Start(appCtx); err != nil {
                if appCtx.Err() == nil {
                    consumerErrCh <- fmt.Errorf("%s failed: %w", name, err)
                }
            }
        }()
    }

    // Start separate consumers for Assigned and Completed queues
    startConsumer("DriverAssigned", brokerConfig.SQS_DRIVER_ASSIGNED_URL)
    startConsumer("TripCompleted", brokerConfig.SQS_TRIP_COMPLETED_URL)

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

    // Wait for OS signal or fatal consumer error
    select {
    case sig := <-stop:
        log.Printf("Received signal %v, shutting down...", sig)
    case err := <-consumerErrCh:
        // [FIXED] Log fatal error but allow the shutdown logic below to run
        log.Printf("CRITICAL CONSUMER ERROR: %v", err)
    }

    // 7. Graceful shutdown sequence
    // First: Stop taking new HTTP requests
    shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 10*time.Second)
    defer shutdownCancel()

    if err := srv.Shutdown(shutdownCtx); err != nil {
        log.Printf("Server shutdown error: %v", err)
    }

    // Second: Signal SQS Consumers to stop polling
    log.Println("Stopping SQS Consumers...")
    appCancel() 
    
    // Give goroutines a moment to finish their last process/delete cycle
    time.Sleep(500 * time.Millisecond)

    log.Println("Server stopped gracefully")
}
