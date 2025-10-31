#!/bin/bash
# Start API in background
python api/app.py &

# Wait for API to be ready
sleep 5

# Start bot in foreground
python bot/main.py
