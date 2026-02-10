# Drive-Ops Smoke Tests

Набір автоматичних smoke tests для перевірки працездатності інфраструктури та сервісів після деплою в AWS.

## Швидкий старт

```bash
# Запустити сервіси в Docker
docker-compose up -d

# Почекати поки сервіси запустяться (30-60 секунд)
sleep 30

# Встановити залежності
pip install -r requirements.txt

# Запустити health check
python health_check.py
```

## Тестування з Docker

Коли сервіси запущені в Docker, вони доступні на localhost:

```bash
# Перевірити що сервіси запущені
docker ps

# Запустити smoke tests
export SMOKE_TRIP_SERVICE_URL=http://localhost:8081
export SMOKE_DRIVER_SERVICE_URL=http://localhost:8082
export SMOKE_CLIENT_GATEWAY_URL=http://localhost:8080

python health_check.py
```

## Доступні тести

### 1. Health Check (`health_check.py`)

Перевіряє доступність усіх сервісів через їх health endpoints.

**Що перевіряє:**
- Trip Service: `GET /health` → HTTP 200 + `{"status":"ok"}`
- Driver Service: `GET /health` → HTTP 200 + `{"status":"ok"}`
- Client Gateway: `GET /` → HTTP 200

**Параметри:**
- `SMOKE_TRIP_SERVICE_URL` - URL Trip Service (обов'язковий)
- `SMOKE_DRIVER_SERVICE_URL` - URL Driver Service (обов'язковий)
- `SMOKE_CLIENT_GATEWAY_URL` - URL Client Gateway (обов'язковий)

**Retry логіка:**
- Таймаут: 10 секунд на запит
- Повторні спроби: 3 спроби з інтервалом 5 секунд

**Exit codes:**
- `0` - всі сервіси працюють
- `1` - хоча б один сервіс недоступний

**Приклад виводу:**
```
======================================================================
  Drive-Ops Health Check Smoke Test
======================================================================

Running health checks...

  Checking Trip Service... ✅
  Checking Driver Service... ✅
  Checking Client Gateway... ✅

Results:

Service              Status          Details
----------------------------------------------------------------------
Trip Service         ✅ OK           trip-service.example.com:8081/health
Driver Service       ✅ OK           driver-service.example.com:8082/health
Client Gateway       ✅ OK           client-gateway.example.com:8080/
----------------------------------------------------------------------

✅ All services are healthy!
```

### 2. SQS Message Flow (планується)

**TODO:** Перевіряє повний цикл асинхронної комунікації через SQS FIFO черги.

### 3. RDS Connectivity (планується)

**TODO:** Перевіряє можливість запису та читання даних з PostgreSQL.

## Використання в різних середовищах

### Development
```bash
export SMOKE_TRIP_SERVICE_URL=http://localhost:8081
export SMOKE_DRIVER_SERVICE_URL=http://localhost:8082
export SMOKE_CLIENT_GATEWAY_URL=http://localhost:8080

python health_check.py
```

### Staging/Production
```bash
# Використати AWS-хости
export SMOKE_TRIP_SERVICE_URL=http://trip-service-staging.internal:8081
export SMOKE_DRIVER_SERVICE_URL=http://driver-service-staging.internal:8082
export SMOKE_CLIENT_GATEWAY_URL=http://gateway-staging.internal:8080

python health_check.py
```

## Інтеграція з CI/CD

Smoke tests можна запускати після деплою через GitHub Actions:

```yaml
- name: Run Smoke Tests
  env:
    SMOKE_TRIP_SERVICE_URL: ${{ secrets.SMOKE_TRIP_SERVICE_URL }}
    SMOKE_DRIVER_SERVICE_URL: ${{ secrets.SMOKE_DRIVER_SERVICE_URL }}
    SMOKE_CLIENT_GATEWAY_URL: ${{ secrets.SMOKE_CLIENT_GATEWAY_URL }}
  run: |
    cd infra/scripts/smoke-tests
    pip install -r requirements.txt
    python health_check.py
```

## Troubleshooting

### Connection timeout
```
❌ Timeout after 10s (tried 3 times)
```
**Можливі причини:**
- Сервіс не запущений
- Неправильний URL або порт
- Firewall/Security Group блокує з'єднання
- Сервіс занадто довго стартує

**Рішення:**
1. Перевірити статус контейнера: `docker ps` або `kubectl get pods`
2. Перевірити логи: `docker logs <container>` або `kubectl logs <pod>`
3. Перевірити Security Groups у AWS
4. Спробувати curl вручну: `curl -v http://<service-url>/health`

### Connection refused
```
❌ Connection error: Connection refused
```
**Можливі причини:**
- Сервіс не слухає на вказаному порту
- Неправильний порт у URL

**Рішення:**
1. Перевірити, чи сервіс працює: `netstat -tulpn | grep <port>`
2. Перевірити конфігурацію порту в Dockerfile/docker-compose.yml

### Invalid JSON response
```
❌ Invalid response: {"status": "error"}
```
**Можливі причини:**
- Сервіс працює, але має проблеми з залежностями (БД, SQS)
- Health endpoint повертає помилку

**Рішення:**
1. Перевірити логи сервісу
2. Перевірити з'єднання з PostgreSQL та SQS
3. Переглянути документацію з діагностики збоїв

## Додаткова інформація

Детальну інформацію про типові збої та способи їх виправлення дивіться у:
- [Smoke Tests Plan](../../../documentation/smoke-tests-plan.md)
- [Smoke Test Failure Modes](../../../documentation/architecture/smoke-test-failure-modes.md) (планується)
