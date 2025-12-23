# TripService CI/CD та Testing

## Огляд

Система тестування для trip-service включає unit та integration тести. Integration тести використовують реальну PostgreSQL базу даних в Docker контейнері для перевірки взаємодії компонентів.

## Локальна розробка

### Запуск unit тестів

Unit тести перевіряють окремі компоненти без зовнішніх залежностей.

```bash
cd trip-service
go test $(go list ./... | grep -v /tests/integration)
```

### Запуск integration тестів

**Передумови:**
- Docker
- Docker Compose

**Команди:**

```bash
# Запустити тестову базу даних
cd trip-service/tests/integration
docker-compose -f docker-compose.test.yml up -d

# Почекати поки PostgreSQL буде готовий (або перевірити статус)
docker logs trip-service-test-db

# Запустити тести
cd ../..
go test -v ./tests/integration/...

# Зупинити тестову базу даних
cd tests/integration
docker-compose -f docker-compose.test.yml down -v
```

**Примітка:** TestMain в `setup_test.go` автоматично запускає і зупиняє Docker Compose, тому ці команди можна використовувати для manual setup.

### Запуск всіх тестів

```bash
cd trip-service
go test ./...
```

## Архітектура integration тестів

### Компоненти

- **PostgreSQL 15** в Docker контейнері
- **Тестова БД:** `trip_service_test`
- **Port:** `5433` (щоб не конфліктувати з локальним PostgreSQL на 5432)
- **Credentials:** `testuser` / `testpass`
- **Контейнер:** `trip-service-test-db`

### Що тестується

1. **Підключення до БД** (`TestDatabaseConnection`)
   - Перевірка що можна підключитися до PostgreSQL
   - Перевірка ping до бази даних

2. **Міграції** (`TestDatabaseMigrations`)
   - Таблиця `trips` існує
   - Enum тип `trip_status` створений
   - Індекс `idx_trips_passenger_id` існує

3. **Repository CRUD операції**
   - `TestTripRepository_Create` - створення trip
   - `TestTripRepository_GetByID` - отримання trip за ID
   - `TestTripRepository_Update` - оновлення trip (статус, driver_id)
   - `TestTripRepository_Delete` - видалення trip

4. **/health endpoint** (`TestHealthEndpoint`)
   - HTTP запит до /health
   - Перевірка 200 OK та JSON response
   - **ПРИМІТКА:** Тест пропускається поки HTTP сервер не буде реалізований

### Ізоляція тестів

- **Кожен запуск** створює новий Docker контейнер
- **Немає persistent volume** - чистий slate кожного разу
- **Кожен тест** очищає свої дані через `t.Cleanup()`
- **Міграції** застосовуються автоматично в TestMain

### Структура файлів

```
trip-service/tests/integration/
├── docker-compose.test.yml    # Docker Compose конфігурація для тестової БД
├── setup_test.go               # TestMain, SetupTestDB, RunMigrations, WaitForDB
├── helpers.go                  # Helper функції (CreateTestTrip, AssertTripEqual, etc.)
└── trip_integration_test.go    # Всі integration тести
```

## CI/CD Pipeline

### Структура Workflow

GitHub Actions workflow містить 3 паралельні jobs:

1. **unit-test** - швидкі unit тести
2. **integration-test** - тести з PostgreSQL
3. **docker-build** - збірка Docker image

Jobs 2 і 3 запускаються паралельно для швидкості. Job 1 (unit-test) запускається незалежно.

### Job 1: Unit Test

**Що робить:**
- Встановлює Go 1.23
- Кешує Go modules
- Запускає unit тести (виключаючи integration)

**Команда:**
```bash
go test $(go list ./... | grep -v /tests/integration)
```

**Час виконання:** ~30 секунд

### Job 2: Integration Test

**Що робить:**
1. Встановлює Go 1.23
2. Кешує Go modules
3. Запускає PostgreSQL через docker-compose
4. Чекає 10 секунд поки БД буде готова
5. Запускає integration тести
6. Зупиняє контейнер (навіть якщо тести failed)

**Environment Variables:**
```yaml
DB_HOST: localhost
DB_PORT: 5433
DB_USER: testuser
DB_PASSWORD: testpass
DB_NAME: trip_service_test
```

**Команда:**
```bash
go test -v ./tests/integration/...
```

**Час виконання:** ~1-2 хвилини

### Job 3: Docker Build

**Що робить:**
1. Встановлює Docker Buildx
2. Логінується в GitHub Container Registry (GHCR)
3. Створює metadata для tags
4. Збирає Docker image з кешуванням
5. Push image (тільки на main branch, не на PR)

**Image Tags:**
- `main-sha-<commit>` - main branch builds
- `<branch>-sha-<commit>` - feature branch builds
- `pr-<number>` - pull request builds

**Push Strategy:**
- **Main branch:** Push до GHCR
- **Pull requests:** Build only, no push (економія місця в registry)

**Cache Strategy:**
- Використовує GitHub Actions cache для Docker layers
- Значно пришвидшує повторні збірки

**ПРИМІТКА:** Цей job зможе працювати тільки після того як буде доданий `trip-service/Dockerfile`.

### Тригери

CI запускається на:
- **Push** до будь-якої гілки з змінами в `trip-service/**`
- **Pull Request** з змінами в `trip-service/**`

### Кешування

**Go Modules:**
- Cache key: `${{ runner.os }}-go-${{ hashFiles('**/go.sum') }}`
- Шлях: `~/.cache/go-build`, `~/go/pkg/mod`
- Пришвидшує встановлення залежностей

**Docker Layers:**
- Cache type: GitHub Actions cache (gha)
- Mode: `max` (кешує всі layers)
- Пришвидшує Docker builds

## Troubleshooting

### Port 5433 вже зайнятий

**Симптом:**
```
Error starting userland proxy: listen tcp4 0.0.0.0:5433: bind: address already in use
```

**Рішення:**
```bash
# Знайти процес що використовує порт
lsof -i :5433

# Або змінити порт в docker-compose.test.yml
ports:
  - "5434:5432"  # Використати інший порт
```

### Docker не запущений

**Симптом:**
```
Cannot connect to the Docker daemon
```

**Рішення:**
```bash
# Linux
sudo systemctl start docker

# macOS
open -a Docker

# Перевірити статус
docker ps
```

### Міграції не застосовуються

**Симптом:**
```
Failed to execute migration: syntax error
```

**Рішення:**
```bash
# Перевірити файли міграцій
ls -la trip-service/db/migrations/

# Перевірити синтаксис SQL
cat trip-service/db/migrations/001_init_trips.up.sql

# Подивитися логи PostgreSQL
docker logs trip-service-test-db

# Підключитися до БД і перевірити вручну
docker exec -it trip-service-test-db psql -U testuser -d trip_service_test
```

### Integration тести падають в CI

**Симптом:**
```
Failed to connect to database: connection refused
```

**Можливі причини:**
1. БД не встигла запуститися (збільшити sleep в CI)
2. Неправильні credentials в environment variables
3. Міграції failed

**Рішення:**
```bash
# Переглянути логи GitHub Actions
gh run view <run-id> --log

# Локально відтворити проблему
cd trip-service/tests/integration
docker-compose -f docker-compose.test.yml up

# В іншому терміналі
cd trip-service
go test -v ./tests/integration/...
```

### TestMain redeclared error

**Симптом:**
```
TestMain redeclared in this block
```

**Причина:**
У вас є два файли з `TestMain` функцією в одному пакеті.

**Рішення:**
Видалити старий/порожній `TestMain`. Тільки `setup_test.go` має містити `TestMain`.

### GORM package not found

**Симптом:**
```
could not import gorm.io/gorm
```

**Рішення:**
```bash
# Створити go.mod якщо не існує
cd trip-service
go mod init github.com/UA-4697-DevOps/drive-ops/trip-service

# Додати залежності
go get gorm.io/gorm
go get gorm.io/driver/postgres
go get github.com/google/uuid

# Або просто запустити тести - Go автоматично завантажить
go test ./...
```

### Docker build fails: Dockerfile not found

**Симптом:**
```
ERROR: failed to solve: failed to read dockerfile
```

**Причина:**
`trip-service/Dockerfile` ще не створений.

**Рішення:**
Цей job буде працювати після того як Dockerfile буде доданий. Build може бути тимчасово disabled або пропущений в PR.

## Debug Commands

### Перевірити тестову базу даних

```bash
# Подивитися чи контейнер запущений
docker ps | grep trip-service-test-db

# Подивитися логи
docker logs trip-service-test-db

# Підключитися до БД
docker exec -it trip-service-test-db psql -U testuser -d trip_service_test

# В psql:
\dt                          # Показати таблиці
\d trips                     # Показати структуру таблиці
\dT                          # Показати типи (enum)
\di                          # Показати індекси
SELECT * FROM trips;         # Показати дані
```

### Перевірити Go environment

```bash
# Версія Go
go version

# Go environment
go env

# Список пакетів
go list ./...

# Залежності
go mod graph
go mod verify
```

### Перевірити CI логи

```bash
# За допомогою GitHub CLI
gh run list --workflow=trip-service-ci.yml

# Переглянути конкретний run
gh run view <run-id>

# Переглянути логи
gh run view <run-id> --log

# Переглянути логи конкретного job
gh run view <run-id> --log --job=integration-test
```

## Best Practices

### Написання тестів

1. **Ізоляція:** Кожен тест має бути незалежним
   ```go
   t.Cleanup(func() {
       testDB.Exec("DELETE FROM trips WHERE id = ?", trip.ID)
   })
   ```

2. **Описові назви:** Використовуйте pattern `Test<Entity>_<Action>`
   ```go
   func TestTripRepository_Create(t *testing.T)
   func TestTripRepository_GetByID(t *testing.T)
   ```

3. **t.Helper():** Використовуйте в helper функціях
   ```go
   func AssertTripEqual(t *testing.T, expected, actual *domain.Trip) {
       t.Helper()  // Помилки будуть вказувати на caller, не на цю функцію
       // ...
   }
   ```

4. **t.Log() для успішних тестів:** Додавайте логування
   ```go
   t.Log("Successfully created trip")
   ```

### Управління даними

1. **Не використовуйте seed data в тестах** - створюйте дані на льоту
2. **Очищайте після себе** - використовуйте `t.Cleanup()`
3. **Використовуйте унікальні IDs** - генеруйте через `uuid.New()`

### CI/CD

1. **Запускайте тести локально перед push**
   ```bash
   go test ./...
   ```

2. **Не commit-ите .env файли** з credentials

3. **Перевіряйте CI логи** якщо тести падають

4. **Використовуйте skip для incomplete features**
   ```go
   t.Skip("Skipping - feature not yet implemented")
   ```

## Метрики та Моніторинг

### Час виконання CI

**Ціль:** < 5 хвилин total

**Поточна структура:**
- Unit tests: ~30 сек
- Integration tests: ~1-2 хв (паралельно з docker-build)
- Docker build: ~1-2 хв (паралельно з integration-test)

**Total:** ~2-3 хвилини (завдяки паралелізації)

### Покриття тестами

**Перевірити покриття:**
```bash
go test -cover ./...
go test -coverprofile=coverage.out ./...
go tool cover -html=coverage.out
```

## Майбутні покращення

1. **Test coverage reporting** - інтеграція з Codecov
2. **Linting в CI** - додати golangci-lint
3. **E2E tests** - тести повного API
4. **Performance tests** - бенчмарки
5. **Makefile** - спростити команди

## Підтримка

Якщо у вас виникли питання або проблеми з тестами:

1. Перевірте цю документацію
2. Подивіться логи (локальні або CI)
3. Створіть issue в GitHub з деталями проблеми
