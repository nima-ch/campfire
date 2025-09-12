#!/bin/bash
set -e

echo "🔥 Starting Campfire Emergency Helper..."

# Configuration validation
echo "📋 Validating configuration..."

# Check required environment variables
required_vars=(
    "CAMPFIRE_CORPUS_DB"
    "CAMPFIRE_AUDIT_DB" 
    "CAMPFIRE_POLICY_PATH"
    "CAMPFIRE_LLM_PROVIDER"
)

for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        echo "❌ Required environment variable $var is not set"
        exit 1
    fi
    echo "✅ $var=${!var}"
done

# Validate corpus database
if [ ! -f "$CAMPFIRE_CORPUS_DB" ]; then
    echo "⚠️  Corpus database not found at $CAMPFIRE_CORPUS_DB"
    echo "📚 Checking for raw documents to ingest..."
    
    if [ -d "/app/corpus/raw" ] && [ "$(ls -A /app/corpus/raw/*.pdf 2>/dev/null)" ]; then
        echo "📄 Found PDF documents, starting ingestion..."
        cd /app
        /app/.venv/bin/python scripts/ingest_corpus.py
        echo "✅ Corpus ingestion complete"
    else
        echo "❌ No corpus database or raw documents found"
        echo "Please mount a corpus database or raw PDF files"
        exit 1
    fi
else
    echo "✅ Corpus database found"
    
    # Verify corpus integrity
    echo "🔍 Verifying corpus integrity..."
    cd /app
    if /app/.venv/bin/python scripts/verify_corpus.py; then
        echo "✅ Corpus verification passed"
    else
        echo "⚠️  Corpus verification failed, but continuing..."
    fi
fi

# Validate policy file
if [ ! -f "$CAMPFIRE_POLICY_PATH" ]; then
    echo "⚠️  Policy file not found at $CAMPFIRE_POLICY_PATH, using defaults"
else
    echo "✅ Policy file found"
fi

# Create audit database directory
mkdir -p "$(dirname "$CAMPFIRE_AUDIT_DB")"

# Validate LLM provider
echo "🤖 Validating LLM provider: $CAMPFIRE_LLM_PROVIDER"
cd /app
if /app/.venv/bin/python -c "
import sys
sys.path.insert(0, '/app/backend/src')
from campfire.llm.factory import get_available_providers
providers = get_available_providers()
available_providers = [p['type'] for p in providers if p['available']]
if '$CAMPFIRE_LLM_PROVIDER' not in available_providers:
    print('❌ LLM provider $CAMPFIRE_LLM_PROVIDER is not available')
    print('Available providers:', available_providers)
    exit(1)
else:
    print('✅ LLM provider $CAMPFIRE_LLM_PROVIDER is available')
"; then
    echo "✅ LLM provider validation passed"
else
    echo "❌ LLM provider validation failed"
    exit 1
fi

# System health check
echo "🏥 Running comprehensive startup health check..."
cd /app
if /app/.venv/bin/python scripts/startup_health_check.py; then
    echo "✅ Comprehensive health check passed"
else
    echo "❌ Comprehensive health check failed"
    exit 1
fi

# Set up graceful shutdown handling
cleanup() {
    echo "🛑 Received shutdown signal, cleaning up..."
    if [ ! -z "$SERVER_PID" ]; then
        echo "Stopping server (PID: $SERVER_PID)..."
        kill -TERM "$SERVER_PID" 2>/dev/null || true
        wait "$SERVER_PID" 2>/dev/null || true
    fi
    echo "👋 Cleanup complete"
    exit 0
}

trap cleanup SIGTERM SIGINT

# Start the server
echo "🚀 Starting Campfire server..."
cd /app

# Use environment variables for server configuration
HOST="${CAMPFIRE_HOST:-0.0.0.0}"
PORT="${CAMPFIRE_PORT:-8000}"
DEBUG="${CAMPFIRE_DEBUG:-false}"

# Build server command
SERVER_CMD="/app/.venv/bin/uvicorn campfire.api.main:app --host $HOST --port $PORT --app-dir backend/src"

if [ "$DEBUG" = "true" ]; then
    SERVER_CMD="$SERVER_CMD --reload --log-level debug"
else
    SERVER_CMD="$SERVER_CMD --log-level info"
fi

echo "📡 Server command: $SERVER_CMD"

# Start server in background to handle signals
$SERVER_CMD &
SERVER_PID=$!

echo "🔥 Campfire Emergency Helper started successfully!"
echo "📡 Server running on http://$HOST:$PORT"
echo "🔒 Offline mode: Enabled"
echo "🤖 LLM Provider: $CAMPFIRE_LLM_PROVIDER"

# Wait for server process
wait "$SERVER_PID"