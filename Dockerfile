# Multi-stage Docker build for Campfire Emergency Helper
# Stage 1: Build frontend
FROM node:18-alpine AS frontend-builder

WORKDIR /app/frontend

# Copy frontend package files
COPY frontend/package*.json ./
RUN npm ci --only=production

# Copy frontend source and build
COPY frontend/ ./
RUN npm run build

# Stage 2: Build backend
FROM python:3.11-slim AS backend-builder

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

WORKDIR /app

# Copy Python project files
COPY pyproject.toml uv.lock LICENSE README.md ./
COPY backend/ ./backend/

# Install Python dependencies
RUN uv sync --no-dev

# Stage 3: Production image
FROM python:3.11-slim AS production

# Install system dependencies for runtime
RUN apt-get update && apt-get install -y \
    curl \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Create app user
RUN useradd --create-home --shell /bin/bash app

# Install uv in production image
RUN pip install uv

WORKDIR /app

# Copy Python environment and code
COPY --from=backend-builder /app/.venv /app/.venv
COPY --from=backend-builder /app/backend /app/backend
COPY --from=backend-builder /app/pyproject.toml /app/uv.lock ./

# Copy frontend build
COPY --from=frontend-builder /app/frontend/build /app/frontend/build

# Copy configuration files
COPY policy.md ./
COPY Makefile ./
COPY scripts/ ./scripts/

# Create necessary directories
RUN mkdir -p /app/corpus/processed /app/corpus/raw /app/data /app/logs

# Set up environment
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/backend/src"
ENV CAMPFIRE_CORPUS_DB="/app/corpus/processed/corpus.db"
ENV CAMPFIRE_AUDIT_DB="/app/data/audit.db"
ENV CAMPFIRE_POLICY_PATH="/app/policy.md"
ENV CAMPFIRE_LLM_PROVIDER="ollama"

# Copy startup and health check scripts
COPY docker/startup.sh /app/startup.sh
COPY docker/healthcheck.sh /app/healthcheck.sh
RUN chmod +x /app/startup.sh /app/healthcheck.sh

# Change ownership to app user
RUN chown -R app:app /app

# Switch to app user
USER app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD /app/healthcheck.sh

# Expose port
EXPOSE 8000

# Start command
CMD ["/app/startup.sh"]