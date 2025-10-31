#!/bin/bash

# ATLAS Quick Start Script
# Starts both API and Bot services

set -e

echo "======================================"
echo "  Starting ATLAS Services"
echo "======================================"
echo ""

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "Error: .env file not found"
    echo "Please run ./setup.sh first"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Error: Virtual environment not found"
    echo "Please run ./setup.sh first"
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Set Python path to allow imports from root directory
export PYTHONPATH="${PWD}:${PYTHONPATH}"

# Ensure logs directory exists
mkdir -p logs

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "Shutting down services..."
    kill $API_PID $BOT_PID 2>/dev/null
    exit
}

trap cleanup SIGINT SIGTERM

# Start API in background
echo "Starting FastAPI backend..."
python api/app.py > logs/api.log 2>&1 &
API_PID=$!
echo "API started (PID: $API_PID)"

# Wait a bit for API to start
sleep 3

# Check if API is healthy
echo "Checking API health..."
if curl -s http://localhost:8000/health > /dev/null; then
    echo "✓ API is healthy"
else
    echo "✗ API health check failed"
    kill $API_PID 2>/dev/null
    exit 1
fi

# Start Bot in background
echo "Starting Telegram bot..."
python bot/main.py > logs/bot.log 2>&1 &
BOT_PID=$!
echo "Bot started (PID: $BOT_PID)"

echo ""
echo "======================================"
echo "  ATLAS Services Running"
echo "======================================"
echo "API:  http://localhost:8000"
echo "Docs: http://localhost:8000/docs"
echo ""
echo "Logs:"
echo "  API: tail -f logs/api.log"
echo "  Bot: tail -f logs/bot.log"
echo ""
echo "Press Ctrl+C to stop all services"
echo "======================================"
echo ""

# Wait for processes
wait $API_PID $BOT_PID
