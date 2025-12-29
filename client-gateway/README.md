# Client Gateway

Telegram bot service for the Drive Ops taxi ordering system.

## Requirements

- Python 3.11+
- Telegram Bot Token

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

3. Edit `bot/.env` to set your Telegram Bot Token and other configurations.

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
