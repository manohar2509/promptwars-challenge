# --------------------------------------------------------------------------
# TravelAI — Multi-stage Docker build for Google Cloud Run
# Uses Python 3.12-slim for minimal image size and non-root user for security.
# --------------------------------------------------------------------------
FROM python:3.12-slim AS base

# Prevent Python from writing .pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

# Install dependencies first (Docker layer caching optimisation)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user for security (CIS Docker Benchmark 4.1)
RUN adduser --disabled-password --no-create-home --gecos "" appuser
USER appuser

EXPOSE 8080

# Health check for Cloud Run readiness probe
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8080/health').raise_for_status()" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--log-level", "info"]
