FROM python:3.13-slim-trixie

WORKDIR /app

RUN useradd -m guest # Create a non-root user

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

USER guest # Switch to non-root user

COPY src ./src

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"] 