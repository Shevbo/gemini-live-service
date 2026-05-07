FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY prisma ./prisma
RUN prisma generate

COPY src ./src
COPY static ./static

RUN mkdir -p /app/audio_storage

ENV PYTHONPATH=/app
ENV HOST=0.0.0.0
ENV PORT=8080

EXPOSE 8080

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
