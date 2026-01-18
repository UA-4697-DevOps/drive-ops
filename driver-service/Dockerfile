# --- Stage 1: Build stage (Тут ми компілюємо залежності) ---
FROM python:3.13-slim-trixie AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Встановлюємо gcc та інструменти збірки
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Створюємо віртуальне середовище
RUN python -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"

COPY requirements.txt .
# Тепер компіляція asyncpg пройде успішно
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# --- Stage 2: Final runtime stage (Чистий і легкий образ) ---
FROM python:3.13-slim-trixie

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/venv/bin:$PATH"

WORKDIR /app

# Встановлюємо лише curl для здоров'я контейнера
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Створюємо безпечного користувача
RUN groupadd --gid 10001 app && \
    useradd --uid 10001 --gid 10001 --create-home --shell /usr/sbin/nologin app

# Копіюємо тільки готове середовище з першої стадії
COPY --from=builder --chown=app:app /app/venv /app/venv
# Копіюємо твій код
COPY --chown=app:app ./src ./src

USER 10001:10001

EXPOSE 8082

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8082/health || exit 1

CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8082"]
