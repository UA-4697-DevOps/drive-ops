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

	api "trip-service/internal/api/http"
	"trip-service/internal/broker"
	"trip-service/internal/repository"
	"trip-service/internal/service"

	"github.com/go-chi/chi/v5"
	"github.com/joho/godotenv"
	httpSwagger "github.com/swaggo/http-swagger/v2"
	"gorm.io/driver/postgres"
	"gorm.io/gorm"

	_ "trip-service/docs" // Import generated docs
)

// @title           Trip Service API
// @version         1.0
// @description     REST API for managing ride trips in Drive-Ops platform
// @description     Handles trip creation, retrieval, driver assignment, and trip lifecycle management
//
// @contact.name    Drive-Ops Team
// @contact.email   support@drive-ops.example.com
//
// @license.name    Apache 2.0
// @license.url     http://www.apache.org/licenses/LICENSE-2.0.html
//
// @host            localhost:8081
// @BasePath        /
//
// @schemes         http https
//
// @tag.name        trips
// @tag.description Operations related to trip management
//
// @tag.name        health
// @tag.description Service health and readiness checks

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

	// Define a background context to manage the entire application lifecycle
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

	// 2. Load Broker Config (Now filtered for SQS only)
	brokerConfig, err := broker.LoadConfig()
	if err != nil {
		log.Fatalf("Failed to load broker config: %v", err)
	}

	// Custom HTTP client for Long Polling (Timeout > 20s)
	customHttpClient := &http.Client{
		Timeout: 30 * time.Second,
	}

	// 3. Initialize AWS Config
	awsCfg, err := config.LoadDefaultConfig(appCtx,
		config.WithRegion(brokerConfig.AWSRegion),
		config.WithHTTPClient(customHttpClient),
	)
	if err != nil {
		log.Fatalf("Failed to load AWS Config: %v", err)
	}

	// 4. Initialize Outbound Publisher (SQS)
	publisher := broker.NewSQSPublisher(awsCfg, brokerConfig.SQS_TRIP_CREATED_URL)
	log.Printf("Successfully initialized SQS Publisher on: %s", brokerConfig.SQS_TRIP_CREATED_URL)

	// 5. Dependency Injection
	repo := repository.NewTripRepository(db)
	svc := service.NewTripService(repo, publisher)
	handler := api.NewTripHandler(svc)

	// --- SQS Consumer Setup ---
	consumerErrCh := make(chan error, 2)

	startConsumer := func(name string, url string) {
		if url == "" {
			log.Printf("WARNING: %s URL is empty. Consumer skipped.", name)
			return
		}
		
		consumer := broker.NewSQSConsumer(awsCfg, url, svc)
		go func() {
			log.Printf("INFO: Starting %s SQS Consumer on: %s", name, url)
			if err := consumer.Start(appCtx); err != nil {
				if appCtx.Err() == nil {
					log.Printf("ERROR: %s failed: %v", name, err)
					consumerErrCh <- fmt.Errorf("%s failed: %w", name, err)
				}
			}
		}()
	}

	// Start separate consumers for Assigned and Completed queues
	startConsumer("DriverAssigned", brokerConfig.SQS_DRIVER_ASSIGNED_URL)
	startConsumer("TripCompleted", brokerConfig.SQS_TRIP_COMPLETED_URL)

	// 6. Router setup
	r := chi.NewRouter()
	r.Get("/health", handler.HealthCheck)
	r.Route("/trips", func(r chi.Router) {
		r.Post("/", handler.CreateTrip)
		r.Get("/{id}", handler.GetTrip)
		r.Patch("/{id}/assign-driver", handler.AssignDriver)
	})

	// Swagger UI - only enabled in non-production environments
	enableSwagger := getEnv("ENABLE_SWAGGER", "false")
	if enableSwagger == "true" {
		log.Println("Swagger UI enabled at /swagger/")
		r.Get("/swagger/*", httpSwagger.WrapHandler)
		r.Get("/openapi.json", func(w http.ResponseWriter, r *http.Request) {
			http.ServeFile(w, r, "./docs/swagger.json")
		})
	} else {
		log.Println("Swagger UI disabled (set ENABLE_SWAGGER=true to enable)")
	}

	// 7. Setup HTTP server with graceful shutdown
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

	select {
	case sig := <-stop:
		log.Printf("Received signal %v, shutting down...", sig)
	case err := <-consumerErrCh:
		log.Printf("CRITICAL CONSUMER ERROR: %v", err)
	}

	// 8. Graceful shutdown sequence
	shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer shutdownCancel()

	if err := srv.Shutdown(shutdownCtx); err != nil {
		log.Printf("Server shutdown error: %v", err)
	}

	log.Println("Stopping SQS Consumers...")
	appCancel() 
	
	time.Sleep(500 * time.Millisecond)
	log.Println("Server stopped gracefully")
}
