FROM python:3.13-slim-trixie

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/app/venv/bin:$PATH"

WORKDIR /app

# Installing curl for the healthcheck process
RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 10001 app && \
    useradd --uid 10001 --gid 10001 --create-home --shell /usr/sbin/nologin app

RUN chown app:app /app
USER 10001:10001

RUN python -m venv /app/venv
COPY --chown=app:app requirements.txt .
RUN pip install -r requirements.txt

COPY --chown=app:app ./src ./src

# Unified service port
EXPOSE 8082

# Docker healthcheck linked to FastAPI's /health endpoint
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8082/health || exit 1

CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8082"]