package integration

import (
    "context"
    "database/sql"
    "fmt"
    "log"
    "os"
	"os/exec"
	"path/filepath"
	"runtime"
	"sort"
    "testing"
    "time"

    _ "github.com/jackc/pgx/v5/stdlib"
    "gorm.io/driver/postgres"
    "gorm.io/gorm"
    "gorm.io/gorm/logger"
)

var (
    testDB *gorm.DB
)

// TestMain sets up the test environment, runs tests, and tears down
func TestMain(m *testing.M) {
    // Inject mandatory AWS SQS variables for the test environment
    // These prevent broker.LoadConfig() from calling log.Fatalf during service init
    if os.Getenv("AWS_REGION") == "" {
        _ = os.Setenv("AWS_REGION", "us-east-2") // Added _ =
    }
    if os.Getenv("SQS_TRIP_CREATED_URL") == "" {
    	_ = os.Setenv("SQS_TRIP_CREATED_URL", "http://mock-sqs/trip-created.fifo")
	}
	// CodeRabbit Fix: Add the missing inbound queue URLs
	if os.Getenv("SQS_DRIVER_ASSIGNED_URL") == "" {
    	_ = os.Setenv("SQS_DRIVER_ASSIGNED_URL", "http://mock-sqs/driver-assigned.fifo")
	}
	if os.Getenv("SQS_TRIP_COMPLETED_URL") == "" {
    	_ = os.Setenv("SQS_TRIP_COMPLETED_URL", "http://mock-sqs/trip-completed.fifo")
	}
    if os.Getenv("AWS_ACCESS_KEY_ID") == "" {
        _ = os.Setenv("AWS_ACCESS_KEY_ID", "mock")
    }
    if os.Getenv("AWS_SECRET_ACCESS_KEY") == "" {
        _ = os.Setenv("AWS_SECRET_ACCESS_KEY", "mock")
    }

    dsn := getTestDSN()

    // Check if database is already running (e.g., in CI with full stack)
    managedCompose := false
    if err := WaitForDB(dsn, 2*time.Second); err != nil {
        // Database not available, start docker-compose
        log.Println("Database not available, starting docker-compose...")
        if err := startDockerCompose(); err != nil {
            log.Fatalf("Failed to start docker-compose: %v", err)
        }
        managedCompose = true

        // Wait for database to be ready
        log.Println("Waiting for PostgreSQL to start...")
        time.Sleep(5 * time.Second) // Give container time to start

        if err := WaitForDB(dsn, 90*time.Second); err != nil {
            stopDockerCompose()
            log.Fatalf("Failed to connect to test database: %v", err)
        }
    } else {
        log.Println("Database already running, skipping docker-compose startup")
    }

    log.Println("PostgreSQL is ready!")

    // Set up database connection
    var err error
    testDB, err = SetupTestDB()
    if err != nil {
        if managedCompose {
            stopDockerCompose()
        }
        log.Fatalf("Failed to setup test database: %v", err)
    }

    // Run migrations
    if err := RunMigrations(testDB); err != nil {
        TearDownTestDB(testDB)
        if managedCompose {
            stopDockerCompose()
        }
        log.Fatalf("Failed to run migrations: %v", err)
    }

    // Run tests
    code := m.Run()

    // Cleanup
    TearDownTestDB(testDB)
    if managedCompose {
        stopDockerCompose()
    }

    os.Exit(code)
}

// SetupTestDB creates and returns a database connection
func SetupTestDB() (*gorm.DB, error) {
    dsn := getTestDSN()

    db, err := gorm.Open(postgres.Open(dsn), &gorm.Config{
        Logger: logger.Default.LogMode(logger.Silent),
    })
    if err != nil {
        return nil, fmt.Errorf("failed to connect to database: %w", err)
    }

    return db, nil
}

// TearDownTestDB closes the database connection
func TearDownTestDB(db *gorm.DB) {
    if db != nil {
        sqlDB, err := db.DB()
        if err == nil {
            _ = sqlDB.Close()
        }
    }
}

// WaitForDB polls the database until it's ready or timeout is reached
func WaitForDB(dsn string, timeout time.Duration) error {
    ctx, cancel := context.WithTimeout(context.Background(), timeout)
    defer cancel()

    ticker := time.NewTicker(2 * time.Second)
    defer ticker.Stop()

    attempt := 0
    for {
        select {
        case <-ctx.Done():
            return fmt.Errorf("timeout waiting for database to be ready after %d attempts", attempt)
        case <-ticker.C:
            attempt++
            db, err := sql.Open("pgx", dsn)
            if err != nil {
                log.Printf("Attempt %d: Failed to open connection: %v", attempt, err)
                continue
            }

            err = db.Ping()
            _ = db.Close()

            if err == nil {
                log.Printf("Successfully connected to database after %d attempts", attempt)
                return nil
            }
            log.Printf("Attempt %d: Ping failed: %v", attempt, err)
        }
    }
}

// RunMigrations executes SQL migrations from the migrations directory
func RunMigrations(db *gorm.DB) error {
    // Check if migrations already applied (e.g., by trip-migrations service in CI)
    var exists bool
    query := `SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name = 'trips'
    )`
    if err := db.Raw(query).Scan(&exists).Error; err != nil {
        return fmt.Errorf("failed to check if migrations applied: %w", err)
    }

    if exists {
        log.Println("Migrations already applied, skipping")
        return nil
    }

    sqlDB, err := db.DB()
    if err != nil {
        return fmt.Errorf("failed to get underlying sql.DB: %w", err)
    }

    // Get path to migrations directory based on project structure
    migrationsPath := filepath.Join("..", "..", "db", "migrations")

    // Read migration files (.up.sql)
    files, err := filepath.Glob(filepath.Join(migrationsPath, "*.up.sql"))
    if err != nil {
        return fmt.Errorf("failed to list migration files: %w", err)
    }

    // Sort files to ensure migrations run in correct order (001, 002, etc.)
    sort.Strings(files)

    // Execute each migration file
    for _, file := range files {
        content, err := os.ReadFile(file)
        if err != nil {
            return fmt.Errorf("failed to read migration file %s: %w", file, err)
        }

        if _, err := sqlDB.Exec(string(content)); err != nil {
            return fmt.Errorf("failed to execute migration %s: %w", file, err)
        }

        log.Printf("Applied migration: %s", filepath.Base(file))
    }

    return nil
}

// getTestDSN returns the database connection string for tests
func getTestDSN() string {
    // Use localhost for tests running outside the container (managedCompose)
    // Matches port 5433 defined in docker-compose.test.yml
    host := getEnv("DB_HOST", "localhost")
    port := getEnv("DB_PORT", "5433") 
    user := getEnv("DB_USER", "testuser")
    password := getEnv("DB_PASSWORD", "testpass")
    
    // Default to the specific test database defined in your test compose
    dbname := getEnv("TRIP_DB_NAME", "trip_service_test")

    return fmt.Sprintf(
        "host=%s port=%s user=%s password=%s dbname=%s sslmode=disable",
        host, port, user, password, dbname,
    )
}

// getEnv returns environment variable value or default if not set
func getEnv(key, defaultValue string) string {
    if value := os.Getenv(key); value != "" {
        return value
    }
    return defaultValue
}

// startDockerCompose starts the test database container
func startDockerCompose() error {
    composePath := getDockerComposePath()
    // Explicitly uses docker-compose.test.yml to avoid production DB conflicts
    cmd := exec.Command("docker", "compose", "-f", composePath, "up", "-d")
    cmd.Stdout = os.Stdout
    cmd.Stderr = os.Stderr

    if err := cmd.Run(); err != nil {
        return fmt.Errorf("docker compose up failed: %w", err)
    }

    log.Println("Started test database container")
    return nil
}

// stopDockerCompose stops and removes the test database container
func stopDockerCompose() {
    composePath := getDockerComposePath()
    // Cleans up volumes (-v) to ensure a fresh state for the next test run
    cmd := exec.Command("docker", "compose", "-f", composePath, "down", "-v")
    cmd.Stdout = os.Stdout
    cmd.Stderr = os.Stderr

    if err := cmd.Run(); err != nil {
        log.Printf("Warning: docker compose down failed: %v", err)
    } else {
        log.Println("Stopped test database container")
    }
}

// getDockerComposePath returns absolute path to docker-compose.test.yml
func getDockerComposePath() string {
    _, filename, _, _ := runtime.Caller(0)
    testDir := filepath.Dir(filename)
    return filepath.Join(testDir, "docker-compose.test.yml")
}
