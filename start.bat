@echo off
REM Start script for Webhook Notification Hub (Windows)

echo Starting Webhook Notification Hub...

REM Check if .env exists
if not exist .env (
    echo Error: .env file not found. Please copy .env.example to .env and configure it.
    exit /b 1
)

REM Check if Redis is running
redis-cli ping >nul 2>&1
if %errorlevel% neq 0 (
    echo Starting Redis...
    start redis-server
    timeout /t 2 /nobreak >nul
)

REM Start Celery worker in new window
echo Starting Celery worker...
start "Celery Worker" python worker.py

REM Start FastAPI server
echo Starting FastAPI server...
python main.py
