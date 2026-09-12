# Quick Start Guide

## Prerequisites
- Python 3.8+ installed
- Redis server running
- GitHub account
- Slack workspace

## 5-Minute Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
cp .env.example .env
```

Edit `.env` and add:
- `GITHUB_WEBHOOK_SECRET`: Create a random string (e.g., `openssl rand -hex 32`)
- `SLACK_WEBHOOK_URL`: Get from Slack App settings

### 3. Start Redis
```bash
redis-server
```

### 4. Start the System

**Terminal 1 - Start Worker:**
```bash
python worker.py
```

**Terminal 2 - Start API:**
```bash
python main.py
```

Or use the provided scripts:
- Windows: `start.bat`
- Linux/Mac: `bash start.sh`

### 5. Test the System

Open dashboard: `http://localhost:8000`

Test webhook (requires proper signature):
```bash
curl -X POST http://localhost:8000/webhook/github \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: push" \
  -H "X-GitHub-Delivery: test-123" \
  -d @test_payload.json
```

## Docker Setup (Alternative)

```bash
docker-compose up -d
```

## Next Steps

1. Set up GitHub webhook in your repository settings
2. Configure Slack incoming webhook
3. Test with a real GitHub push event
4. Monitor the dashboard

## Troubleshooting

**Redis connection error**: Make sure Redis is running (`redis-cli ping`)

**Import errors**: Run `pip install -r requirements.txt` again

**Port already in use**: Change `PORT` in `.env` or stop the conflicting service
