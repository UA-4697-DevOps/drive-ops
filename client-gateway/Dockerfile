FROM python:3.11-slim

# Налаштування середовища для Python:
# 1. Заборона створення .pyc файлів
# 2. Негайний вивід логів без буферизації
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Встановлюємо системні залежності (curl для healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Створення безпечного non-root користувача
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# Копіюємо залежності та встановлюємо їх
COPY --chown=appuser:appuser requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копіюємо код бота
COPY --chown=appuser:appuser bot/ ./bot/

# Відкриваємо порт 8080 для Notification Server (FastAPI)
# Це критично для Phase 2 та Phase 4 (Push Notifications)
EXPOSE 8080

USER appuser

# Healthcheck для перевірки працездатності HTTP-сервера всередині бота
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1

ENTRYPOINT [ "python", "-m", "bot.main" ]
