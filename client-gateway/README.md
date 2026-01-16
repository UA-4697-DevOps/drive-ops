# Client Gateway

Telegram bot service for the Drive Ops taxi ordering system.

## Features

### Passenger Features
- Role selection (Passenger/Driver)
- Trip ordering with pickup and dropoff addresses
- Optional trip comments
- Rate information display
- Order tracking

### Driver Features
- **Driver Registration** - Two-step registration process (name + car description)
- **Online/Offline Status Management** - Control availability for receiving orders
- **Status Display** - View current driver status and information
- **Order Management** - View and accept/decline trip requests

For detailed information about driver features, see [DRIVER_REGISTRATION.md](DRIVER_REGISTRATION.md).

## Requirements

- Python 3.11+
- Telegram Bot Token
- Trip Service (for passenger trip requests)
- Driver Service (for driver registration and status management)

## Setup

0. Get your Telegram Bot Token by creating a bot with BotFather on Telegram.

1. cd into client-gateway directory:
   ```bash
   cd client-gateway
   ```

2. Copy the example environment file:
   ```bash
   cp bot/.env.example bot/.env
   ```

3. Edit `bot/.env` to set your Telegram Bot Token and service URLs:
   ```bash
   BOT_TOKEN=your_telegram_bot_token_here
   TRIP_SERVICE_URL=http://trip-service:8080
   DRIVER_SERVICE_URL=http://driver-service:8081
   ```

## Running Locally

Install dependencies:
```bash
pip install -r requirements.txt
```

```bash
python bot/main.py
```

## Running with Docker

Build the image:
```bash
docker build -t client-gateway .
```

Run the container (first time):
```bash
docker run --name client-gateway-bot --env-file bot/.env client-gateway
```

Start the existing container (subsequent runs):
```bash
docker start -a client-gateway-bot
```

## Testing

Run all tests:
```bash
cd client-gateway
python -m pytest tests/ -v
```

Run specific test suites:
```bash
# Driver registration tests
python -m pytest tests/test_driver_registration.py -v

# Telegram utilities tests
python -m pytest tests/test_telegram_utils.py -v
```

## Architecture

The Client Gateway acts as the user interface layer, communicating with backend services:

```
User (Telegram) ↔ Client Gateway ↔ Trip Service (passenger trips)
                                 ↔ Driver Service (driver management)
```

### Key Components

- **bot/main.py** - Bot initialization, configuration, and helper functions
- **bot/driver.py** - Driver registration and status management handlers
- **bot/passenger.py** - Passenger trip ordering handlers
- **bot/logger_utils.py** - Logging utilities and correlation ID generation

## Documentation

- [DRIVER_REGISTRATION.md](DRIVER_REGISTRATION.md) - Driver registration and status management feature
- [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) - Implementation details and statistics
