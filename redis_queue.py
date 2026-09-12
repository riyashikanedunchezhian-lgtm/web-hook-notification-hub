import redis
from celery import Celery
from config import settings
import json
from typing import Optional
from datetime import datetime


# Redis client for simple operations
redis_client = redis.from_url(settings.redis_url, decode_responses=True)

# Celery app for task queue
celery_app = Celery(
    'webhook_hub',
    broker=settings.redis_url,
    backend=settings.redis_url
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=50,
)


class IdempotencyManager:
    """Manages idempotency to prevent duplicate event processing."""
    
    @staticmethod
    def is_duplicate(idempotency_key: str) -> bool:
        """Check if an event with this idempotency key has already been processed."""
        key = f"idempotency:{idempotency_key}"
        return redis_client.exists(key) > 0
    
    @staticmethod
    def mark_processed(idempotency_key: str, ttl: int = 86400) -> None:
        """Mark an event as processed with a TTL (default 24 hours)."""
        key = f"idempotency:{idempotency_key}"
        redis_client.setex(key, ttl, "1")
    
    @staticmethod
    def get_event_id(idempotency_key: str) -> Optional[str]:
        """Get the event ID for a given idempotency key."""
        key = f"idempotency_event:{idempotency_key}"
        return redis_client.get(key)
    
    @staticmethod
    def store_event_id(idempotency_key: str, event_id: str, ttl: int = 86400) -> None:
        """Store the event ID for an idempotency key."""
        key = f"idempotency_event:{idempotency_key}"
        redis_client.setex(key, ttl, event_id)


class EventStore:
    """Stores event history in Redis."""
    
    @staticmethod
    def save_event(event_data: dict) -> None:
        """Save event data to Redis."""
        key = f"event:{event_data['id']}"
        redis_client.setex(key, 604800, json.dumps(event_data))  # 7 days TTL
        
        # Add to recent events list
        redis_client.lpush("recent_events", event_data['id'])
        redis_client.ltrim("recent_events", 0, 99)  # Keep only last 100
    
    @staticmethod
    def get_event(event_id: str) -> Optional[dict]:
        """Get event data by ID."""
        key = f"event:{event_id}"
        data = redis_client.get(key)
        if data:
            return json.loads(data)
        return None
    
    @staticmethod
    def get_recent_events(limit: int = 50) -> list:
        """Get recent events."""
        event_ids = redis_client.lrange("recent_events", 0, limit - 1)
        events = []
        for event_id in event_ids:
            event = EventStore.get_event(event_id)
            if event:
                events.append(event)
        return events
    
    @staticmethod
    def update_event_status(event_id: str, status: str, error_message: Optional[str] = None) -> None:
        """Update event status."""
        key = f"event:{event_id}"
        data = redis_client.get(key)
        if data:
            event = json.loads(data)
            event['status'] = status
            if error_message:
                event['error_message'] = error_message
            if status in ['success', 'failed']:
                event['processed_at'] = datetime.utcnow().isoformat()
            redis_client.setex(key, 604800, json.dumps(event))
