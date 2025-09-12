#!/bin/bash
set -e

# Health check script for Docker container
HOST="${CAMPFIRE_HOST:-0.0.0.0}"
PORT="${CAMPFIRE_PORT:-8000}"

# If host is 0.0.0.0, use localhost for health check
if [ "$HOST" = "0.0.0.0" ]; then
    CHECK_HOST="localhost"
else
    CHECK_HOST="$HOST"
fi

HEALTH_URL="http://$CHECK_HOST:$PORT/health"

# Check if server is responding
if curl -f -s "$HEALTH_URL" > /dev/null 2>&1; then
    # Get detailed health status
    HEALTH_RESPONSE=$(curl -s "$HEALTH_URL")
    
    # Check if response contains "healthy" status
    if echo "$HEALTH_RESPONSE" | grep -q '"status":"healthy"'; then
        echo "✅ Health check passed - system healthy"
        exit 0
    elif echo "$HEALTH_RESPONSE" | grep -q '"status":"degraded"'; then
        echo "⚠️  Health check warning - system degraded"
        echo "$HEALTH_RESPONSE"
        exit 0  # Still considered healthy for Docker
    else
        echo "❌ Health check failed - unhealthy status"
        echo "$HEALTH_RESPONSE"
        exit 1
    fi
else
    echo "❌ Health check failed - server not responding"
    exit 1
fi