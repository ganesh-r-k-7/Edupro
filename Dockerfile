# Dockerfile — Multi-stage build for EduPro API

# ─── Build Stage ────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml requirements.lock* ./

# Install dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.lock

# Copy source code
COPY src/ ./src/

# Install package in development mode
RUN pip install --no-cache-dir -e .


# ─── Runtime Stage ──────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r edupro && useradd -r -g edupro -d /app -s /sbin/nologin edupro

# Set working directory
WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY --from=builder /app/src ./src
COPY --from=builder /app/models ./models

# Create directories for data and registry with correct permissions
RUN mkdir -p /app/data /app/models/registry && \
    chown -R edupro:edupro /app

# Switch to non-root user
USER edupro

# Environment variables (can be overridden at runtime)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ENVIRONMENT=production \
    API_HOST=0.0.0.0 \
    API_PORT=8000 \
    DATA_DIR=/app/data \
    MODELS_DIR=/app/models \
    REGISTRY_DIR=/app/models/registry \
    LOG_FORMAT=json \
    LOG_LEVEL=INFO

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health/live || exit 1

# Run the API server
CMD ["uvicorn", "edup.api.main:app", "--host", "0.0.0.0", "--port", "8000"]