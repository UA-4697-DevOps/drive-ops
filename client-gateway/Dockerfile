# --- Stage 1: Build stage (Компіляція) ---
FROM python:3.13-slim-trixie AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Встановлюємо залежності для збірки
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Віртуальне середовище
RUN python -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# --- Stage 2: Final runtime stage (Запуск) ---
FROM python:3.13-slim-trixie

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/venv/bin:$PATH"

WORKDIR /app

# Curl для healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Користувач
RUN groupadd --gid 10001 app && \
    useradd --uid 10001 --gid 10001 --create-home --shell /usr/sbin/nologin app

# Копіюємо віртуальне середовище
COPY --from=builder --chown=app:app /app/venv /app/venv

# !!! ВИПРАВЛЕННЯ: Копіюємо папку 'bot', а не 'src' !!!
COPY --chown=app:app ./bot ./bot

USER 10001:10001

# !!! ВИПРАВЛЕННЯ: Порт 8080 (як у main.py), а не 8082 !!!
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1

# !!! ВИПРАВЛЕННЯ: Запускаємо модуль бота, а не просто uvicorn !!!
CMD ["python", "-m", "bot.main"]
