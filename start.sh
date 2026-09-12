#!/bin/bash

# Start script for Webhook Notification Hub

echo "Starting Webhook Notification Hub..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "Error: .env file not found. Please copy .env.example to .env and configure it."
    exit 1
fi

# Check if Redis is running
if ! redis-cli ping > /dev/null 2>&1; then
    echo "Starting Redis..."
    redis-server --daemonize yes
    sleep 2
fi

# Start Celery worker in background
echo "Starting Celery worker..."
python worker.py &
WORKER_PID=$!

# Start FastAPI server
echo "Starting FastAPI server..."
python main.py

# Cleanup on exit
trap "kill $WORKER_PID" EXIT
