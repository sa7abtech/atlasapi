#!/bin/bash
set -e

# Start API in background
python api/app.py &
API_PID=$!

# Wait for API to be ready (health check)
echo "Waiting for API to start..."
export API_URL="http://localhost:${PORT:-8000}"

for i in {1..30}; do
  if curl -s "$API_URL/health" > /dev/null 2>&1; then
    echo "API is ready!"
    break
  fi
  echo "Waiting for API... ($i/30)"
  sleep 2
done

# Check if API is actually running
if ! curl -s "$API_URL/health" > /dev/null 2>&1; then
  echo "ERROR: API failed to start"
  exit 1
fi

# Start bot in foreground
python bot/main.py
