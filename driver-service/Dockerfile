FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src

CMD ["./wait-for-it.sh", "db:5432", "--", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
