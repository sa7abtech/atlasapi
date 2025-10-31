#!/bin/bash
# Start API in background
python api/app.py &

# Wait for API to be ready
sleep 5

# Set internal API URL for bot
export API_URL="http://localhost:${PORT:-8000}"

# Start bot in foreground
python bot/main.py
