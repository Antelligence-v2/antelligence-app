# Multi-stage Dockerfile for Production Deployment
# Optimized for AWS deployment with security and performance improvements

# Stage 1: Frontend build
FROM node:18-alpine AS frontend-builder

# Build argument to force cache invalidation
ARG BUILD_TIMESTAMP
ARG BUILD_VERSION=latest

# Set working directory
WORKDIR /app/frontend

# Copy frontend package files first for better caching
COPY frontend/package*.json ./

# Install ALL dependencies (including dev dependencies needed for build)
RUN npm ci --silent && npm cache clean --force

# Copy ALL frontend source files (except node_modules and dist per .dockerignore)
# This COPY will invalidate cache if any frontend source files change
COPY frontend/ ./

# Build frontend to static files with optimizations
# Force rebuild by using build args (changes every build)
RUN echo "Build timestamp: ${BUILD_TIMESTAMP:-$(date -u +'%Y-%m-%dT%H:%M:%SZ')}" && \
    echo "Build version: ${BUILD_VERSION}" && \
    npm run build && \
    echo "✅ Frontend build completed at $(date -u +'%Y-%m-%dT%H:%M:%SZ')"

# Stage 2: Backend with frontend static files
FROM python:3.11-slim AS backend-prod

# Set working directory
WORKDIR /app

# Install system dependencies with security updates
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && apt-get upgrade -y \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Create non-root user for security
RUN groupadd -r antelligence && useradd -r -g antelligence antelligence

# Copy backend requirements
COPY backend/requirements.txt .

# Install Python dependencies with optimizations
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip cache purge

# Copy backend source code
COPY backend/ ./backend/

# Copy blockchain client folder (make sure this folder exists before building)
COPY blockchain/ ./blockchain/

# Copy built frontend static files from stage 1
COPY --from=frontend-builder /app/frontend/dist ./static

# Create .env template (will be overridden by environment variables in production)
RUN echo "# Backend Environment Configuration\n\
# API Configuration\n\
IO_SECRET_KEY=\n\
OPENAI_API_KEY=\n\
GEMINI_API_KEY=\n\
MISTRAL_API_KEY=\n\
\n\
# Blockchain Configuration (Base Sepolia Testnet)\n\
BASE_SEPOLIA_RPC_URL=\n\
CHAIN_RPC=\n\
PRIVATE_KEY=\n\
FOOD_ADDR=\n\
MEMORY_ADDR=\n\
TUMOR_INTEL_ADDR=" > .env

# Set Python path and production environment
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Set proper permissions
RUN chown -R antelligence:antelligence /app
USER antelligence

# Expose port
EXPOSE 8001

# Health check with better error handling
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Start the application with production optimizations
CMD ["python", "-m", "uvicorn", "backend.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8001", \
     "--workers", "1", \
     "--access-log", \
     "--log-level", "info"]