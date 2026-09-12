# Webhook Notification Hub

A production-ready webhook-driven notification system that connects GitHub webhooks to Slack notifications with proper security, idempotency, rate limiting, and retry logic.

## Features

- **Secure Webhook Verification**: HMAC-SHA256 signature verification for GitHub webhooks
- **Decoupled Processing**: Redis-backed queue with Celery workers for async processing
- **Idempotency Handling**: Prevents duplicate event processing using idempotency keys
- **Rate Limiting**: Built-in rate limiting for outgoing API calls
- **Retry Logic**: Exponential backoff retry mechanism for failed notifications
- **Real-time Dashboard**: Web interface to monitor event history, status, and retry failed events
- **Multiple Source Support**: Extensible architecture for adding more webhook sources

## Architecture

```
GitHub Webhook → FastAPI → Signature Verification → Redis Queue → Celery Worker → Slack
                                    ↓
                              Event Store (Redis)
                                    ↓
                              Dashboard (FastAPI + Jinja2)
```

## Setup

### Prerequisites

- Python 3.8+
- Redis server
- GitHub account (for webhook setup)
- Slack workspace (for incoming webhook)

### Installation

1. Clone the repository and install dependencies:

```bash
pip install -r requirements.txt
```

2. Copy the example environment file and configure:

```bash
cp .env.example .env
```

Edit `.env` with your actual values:
- `GITHUB_WEBHOOK_SECRET`: Secret from GitHub webhook configuration
- `SLACK_WEBHOOK_URL`: Incoming webhook URL from Slack
- `REDIS_URL`: Redis connection string (default: `redis://localhost:6379/0`)

### Running the System

1. Start Redis (if not already running):
```bash
redis-server
```

2. Start the Celery worker (in a separate terminal):
```bash
python worker.py
```

3. Start the FastAPI server:
```bash
python main.py
```

The dashboard will be available at `http://localhost:8000`

### GitHub Webhook Setup

1. Go to your GitHub repository Settings → Webhooks
2. Click "Add webhook"
3. Payload URL: `http://your-server:8000/webhook/github`
4. Content type: `application/json`
5. Secret: Use the same value as `GITHUB_WEBHOOK_SECRET` in your `.env`
6. Events: Select "Push" events (or others as needed)
7. Click "Add webhook"

### Slack Webhook Setup

1. Go to https://api.slack.com/apps
2. Create a new app → "Incoming Webhooks"
3. Activate incoming webhooks
4. Add new webhook to your workspace/channel
5. Copy the webhook URL to `SLACK_WEBHOOK_URL` in your `.env`

## API Endpoints

- `GET /` - Dashboard with event history
- `POST /webhook/github` - GitHub webhook endpoint
- `GET /health` - Health check endpoint
- `GET /api/events` - Get recent events
- `GET /api/events/{event_id}` - Get specific event details
- `POST /api/events/{event_id}/retry` - Manually retry a failed event

## Edge Cases and Solutions

### 1. Expired or Invalid Webhook Signatures

**Problem**: GitHub webhooks include a signature for security, but if the secret is misconfigured or the signature is malformed, the webhook will be rejected.

**Solution**: 
- Implemented constant-time HMAC comparison in `webhook_security.py` to prevent timing attacks
- Graceful error handling that returns 403 Forbidden with clear error message
- Verification happens before any processing to avoid wasted resources
- Logs failed verification attempts for debugging

**Code Reference**: `webhook_security.py:verify_github_signature()`

### 2. Duplicate Webhook Events

**Problem**: GitHub may redeliver webhooks if it doesn't receive a timely response, leading to duplicate notifications in Slack.

**Solution**:
- Implemented idempotency using GitHub's `X-GitHub-Delivery` header as a unique key
- Redis-based idempotency check with 24-hour TTL
- Events are marked as processed in Redis before actual processing
- Duplicate detection happens immediately, before queuing
- Returns the original event ID for duplicates

**Code Reference**: `queue.py:IdempotencyManager`, `main.py:github_webhook()`

### 3. Malformed or Invalid JSON Payloads

**Problem**: Webhooks may contain malformed JSON or unexpected payload structures, causing processing failures.

**Solution**:
- JSON validation at the webhook endpoint before processing
- Try-catch blocks around JSON parsing with clear error messages
- Event store records the raw payload for debugging
- Failed events can be inspected via the dashboard API
- Manual retry capability after fixing issues

**Code Reference**: `main.py:github_webhook()` - JSONDecodeError handling

### 4. Rate Limiting on Outgoing API Calls

**Problem**: Slack has rate limits on incoming webhooks. Burst webhook events could trigger rate limits and cause failures.

**Solution**:
- Implemented Redis-based rate limiter with sliding window
- Configurable limits (default: 20 requests per 60 seconds)
- Rate limit check before each Slack notification
- Events are queued and retried if rate limited
- Dashboard shows retry count for rate-limited events

**Code Reference**: `notifications.py:RateLimiter`

### 5. Temporary Network Failures

**Problem**: Network issues or Slack downtime can cause notification failures, but the issue might be transient.

**Solution**:
- Exponential backoff retry logic (1s, 2s, 4s delays)
- Maximum of 3 retries per event
- Async HTTP client with timeout handling
- Failed events can be manually retried via dashboard
- Retry count tracked and displayed

**Code Reference**: `notifications.py:SlackNotifier.send_notification()`, `tasks.py:process_webhook()`

### 6. Redis Connection Failures

**Problem**: If Redis is unavailable, the system cannot queue events or track idempotency.

**Solution**:
- Health check endpoint (`/health`) monitors Redis connectivity
- Events are saved to Redis with TTL to prevent memory bloat
- Worker handles Redis connection errors gracefully
- Dashboard shows system health status
- Redis operations wrapped in try-catch with appropriate error handling

**Code Reference**: `main.py:health_check()`, `queue.py` - Redis operations

## Testing

### Manual Testing

1. Test webhook signature verification:
```bash
curl -X POST http://localhost:8000/webhook/github \
  -H "Content-Type: application/json" \
  -H "X-Hub-Signature-256: sha256=invalid_signature" \
  -d '{"test": "data"}'
```

2. Test health check:
```bash
curl http://localhost:8000/health
```

3. Test event retrieval:
```bash
curl http://localhost:8000/api/events
```

### Automated Testing

Create a test webhook payload:
```bash
curl -X POST http://localhost:8000/webhook/github \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: push" \
  -H "X-GitHub-Delivery: test-123" \
  -d @test_payload.json
```

## Monitoring

The dashboard provides:
- Real-time event history
- Success/failure statistics
- Event status tracking (pending, processing, success, failed, retrying)
- Retry counts for failed events
- Manual retry functionality
- Auto-refresh capability

## Security Considerations

1. **Signature Verification**: Always verify webhook signatures before processing
2. **Secrets Management**: Never commit `.env` file; use environment variables in production
3. **Rate Limiting**: Prevent abuse and protect downstream services
4. **Input Validation**: Validate all incoming payloads
5. **Error Handling**: Don't expose sensitive information in error messages
6. **HTTPS**: Use HTTPS in production for webhook endpoints

## Production Deployment

For production deployment:

1. Use a process manager (systemd, supervisor) for the worker and API server
2. Configure proper logging (file-based, not just console)
3. Use environment-specific configuration
4. Set up monitoring and alerting
5. Use a proper Redis instance (not localhost)
6. Configure CORS if needed
7. Set up proper firewall rules
8. Use a WAF for additional security
9. Configure backup and recovery for Redis

## Troubleshooting

**Webhook not received**: Check GitHub webhook delivery logs in repository settings

**Signature verification failing**: Ensure `GITHUB_WEBHOOK_SECRET` matches GitHub webhook secret exactly

**Events not processing**: Check Celery worker logs, ensure Redis is running

**Slack notifications failing**: Check `SLACK_WEBHOOK_URL` is correct, verify Slack webhook is active

**Redis connection errors**: Ensure Redis server is running and accessible

## License

MIT License - feel free to use this as a template for your own webhook systems.
