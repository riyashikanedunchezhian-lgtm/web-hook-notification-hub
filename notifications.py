import httpx
import asyncio
from typing import Optional
from datetime import datetime, timedelta
from config import settings
import json


class RateLimiter:
    """Simple rate limiter using Redis."""
    
    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
    
    async def acquire(self, key: str) -> bool:
        """Try to acquire a rate limit slot."""
        from queue import redis_client
        
        current_time = datetime.utcnow().timestamp()
        window_start = current_time - self.window_seconds
        
        # Clean up old entries
        redis_client.zremrangebyscore(key, 0, window_start)
        
        # Check current count
        current_count = redis_client.zcard(key)
        
        if current_count >= self.max_requests:
            return False
        
        # Add current request
        redis_client.zadd(key, {str(current_time): current_time})
        redis_client.expire(key, self.window_seconds)
        
        return True


class SlackNotifier:
    """Handles sending notifications to Slack."""
    
    def __init__(self):
        self.webhook_url = settings.slack_webhook_url
        self.channel = settings.slack_channel
        self.rate_limiter = RateLimiter(max_requests=20, window_seconds=60)
    
    async def send_notification(self, message: str, event_data: dict) -> dict:
        """Send a notification to Slack with retry logic."""
        rate_limit_key = f"slack_rate_limit"
        
        # Check rate limit
        if not await self.rate_limiter.acquire(rate_limit_key):
            return {
                "success": False,
                "error": "Rate limit exceeded"
            }
        
        payload = {
            "channel": self.channel,
            "text": message,
            "attachments": [
                {
                    "color": "good" if event_data.get("status") == "success" else "danger",
                    "fields": [
                        {
                            "title": "Event Type",
                            "value": event_data.get("event_type", "Unknown"),
                            "short": True
                        },
                        {
                            "title": "Source",
                            "value": event_data.get("source", "Unknown"),
                            "short": True
                        },
                        {
                            "title": "Received At",
                            "value": event_data.get("received_at", ""),
                            "short": True
                        },
                        {
                            "title": "Status",
                            "value": event_data.get("status", "pending"),
                            "short": True
                        }
                    ]
                }
            ]
        }
        
        # Retry logic with exponential backoff
        max_retries = 3
        base_delay = 1  # seconds
        
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(
                        self.webhook_url,
                        json=payload,
                        headers={"Content-Type": "application/json"}
                    )
                    
                    if response.status_code == 200:
                        return {"success": True, "status_code": response.status_code}
                    else:
                        if attempt < max_retries - 1:
                            delay = base_delay * (2 ** attempt)
                            await asyncio.sleep(delay)
                        else:
                            return {
                                "success": False,
                                "error": f"HTTP {response.status_code}",
                                "response": response.text
                            }
            
            except httpx.TimeoutError:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
                else:
                    return {"success": False, "error": "Timeout"}
            
            except httpx.HTTPError as e:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
                else:
                    return {"success": False, "error": str(e)}
        
        return {"success": False, "error": "Max retries exceeded"}


class GitHubEventHandler:
    """Handles GitHub webhook events."""
    
    @staticmethod
    def parse_push_event(payload: dict) -> dict:
        """Parse a GitHub push event."""
        return {
            "repository": payload.get("repository", {}).get("full_name", "Unknown"),
            "pusher": payload.get("pusher", {}).get("name", "Unknown"),
            "ref": payload.get("ref", "Unknown"),
            "commits": len(payload.get("commits", [])),
            "head_commit": payload.get("head_commit", {}).get("message", "No message"),
            "compare_url": payload.get("compare", "")
        }
    
    @staticmethod
    def format_slack_message(event_data: dict) -> str:
        """Format a GitHub event for Slack."""
        parsed = GitHubEventHandler.parse_push_event(event_data)
        
        return (
            f"🚀 New push to *{parsed['repository']}*\n"
            f"Branch: {parsed['ref']}\n"
            f"Pushed by: {parsed['pusher']}\n"
            f"Commits: {parsed['commits']}\n"
            f"Latest commit: {parsed['head_commit'][:50]}..."
        )
