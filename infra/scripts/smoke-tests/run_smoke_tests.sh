#!/bin/bash
# Wrapper script to run smoke tests with environment variables from .env file

set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$(dirname "$SCRIPT_DIR")")")"

# Load environment variables from .env file if it exists
if [ -f "$PROJECT_ROOT/.env" ]; then
    echo "Loading environment variables from $PROJECT_ROOT/.env"
    set -a
    source "$PROJECT_ROOT/.env"
    set +a
else
    echo "Warning: .env file not found at $PROJECT_ROOT/.env"
fi

# Activate virtual environment if it exists
if [ -f "$PROJECT_ROOT/.venv/bin/activate" ]; then
    echo "Activating virtual environment..."
    source "$PROJECT_ROOT/.venv/bin/activate"
fi

# Check if required smoke test variables are set
REQUIRED_VARS=("SMOKE_TRIP_SERVICE_URL" "SMOKE_DRIVER_SERVICE_URL" "BOT_TOKEN")

missing_vars=()
for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        missing_vars+=("$var")
    fi
done

if [ ${#missing_vars[@]} -ne 0 ]; then
    echo "Error: Missing required environment variables:"
    for var in "${missing_vars[@]}"; do
        echo "  - $var"
    done
    echo ""
    echo "Please set them in your .env file or export them manually:"
    echo "  export SMOKE_TRIP_SERVICE_URL=http://your-trip-service:8081"
    echo "  export SMOKE_DRIVER_SERVICE_URL=http://your-driver-service:8082"
    echo "  export BOT_TOKEN=your_telegram_bot_token"
    exit 1
fi

# Run the health check
echo "Running smoke tests..."

# 1. Health Check Test  
echo "1. Running Health Check..."
python "$SCRIPT_DIR/health_check.py"

# 2. SQS Message Flow Test (in degraded mode for local testing)
echo ""
echo "2. Running SQS Message Flow Test (degraded mode)..."
export SQS_FLOW_DEGRADED_MODE=true
python "$SCRIPT_DIR/sqs_flow_test.py"

echo ""
echo "All smoke tests completed successfully!"
python "$SCRIPT_DIR/health_check.py"