FROM python:3.13-slim-trixie

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src \
    PATH="/app/venv/bin:$PATH"

WORKDIR /app

RUN groupadd --gid 10001 app && \
    useradd --uid 10001 --gid 10001 --create-home --shell /usr/sbin/nologin app

RUN chown app:app /app

USER 10001:10001

RUN python -m venv /app/venv

COPY --chown=app:app requirements.txt .
RUN pip install -r requirements.txt

COPY --chown=app:app ./src ./src

EXPOSE 8082

WORKDIR /app/src

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8082"]
