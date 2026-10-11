# Multi-stage Dockerfile for PersonalMail AI
# Stage 1: Build Frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Stage 2: Python Backend & Final Application
FROM python:3.11-slim
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LANGMAIL_DATA_DIR=/app/data

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -e .

# Copy source code and built frontend assets
COPY src/ ./src/
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Expose FastAPI port
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/auth/status || exit 1

# Start server
CMD ["python", "-m", "uvicorn", "langmail.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
