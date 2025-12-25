# ============================================================================
# MICROBOT API Server - Production Dockerfile
# ============================================================================
# Build: docker build -t microbot-api .
# Run:   docker run -p 5000:5000 --env-file .env microbot-api
# ============================================================================

# Multi-stage build for optimized production image
FROM python:3.11-slim as builder

# Set working directory
WORKDIR /app

# Install system dependencies for audio processing and compilation
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    libportaudio2 \
    libportaudiocpp0 \
    portaudio19-dev \
    python3-dev \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ============================================================================
# Production stage - minimal runtime image
# ============================================================================
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install runtime dependencies only (no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libportaudio2 \
    ffmpeg \
    libsndfile1 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Create non-root user for security
RUN useradd -m -u 1000 microbot && \
    mkdir -p /app/logs && \
    chown -R microbot:microbot /app

# Copy application code (exclude unnecessary files)
COPY --chown=microbot:microbot api_server.py .
COPY --chown=microbot:microbot microbot/ ./microbot/
COPY --chown=microbot:microbot config.json .
COPY --chown=microbot:microbot requirements.txt .

# Copy data files (will be overwritten by volume mounts in production)
COPY --chown=microbot:microbot notes.json .
COPY --chown=microbot:microbot reminders.json .
COPY --chown=microbot:microbot personal_memory.json .

# Switch to non-root user
USER microbot

# Expose port
EXPOSE 5000

# Health check for container orchestration
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:5000/api/health || exit 1

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=5000 \
    PYTHONIOENCODING=utf-8

# Run the application
CMD ["python", "api_server.py"]
