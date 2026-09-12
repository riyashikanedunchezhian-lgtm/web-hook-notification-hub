from celery import current_task
from redis_queue import celery_app, EventStore, IdempotencyManager
from notifications import SlackNotifier, GitHubEventHandler
from models import EventStatus
import json


@celery_app.task(bind=True, max_retries=3)
def process_webhook(self, event_id: str, event_data: dict):
    """
    Process a webhook event asynchronously.
    This task is queued by the webhook endpoint and executed by a Celery worker.
    """
    try:
        # Update status to processing
        EventStore.update_event_status(event_id, EventStatus.PROCESSING.value)
        
        # Check idempotency
        idempotency_key = event_data.get("idempotency_key")
        if idempotency_key and IdempotencyManager.is_duplicate(idempotency_key):
            EventStore.update_event_status(
                event_id, 
                EventStatus.SUCCESS.value,
                "Duplicate event, already processed"
            )
            return {"status": "duplicate", "event_id": event_id}
        
        # Process based on source
        source = event_data.get("source")
        
        if source == "github":
            # Format message for Slack
            message = GitHubEventHandler.format_slack_message(event_data["payload"])
            
            # Send to Slack
            notifier = SlackNotifier()
            result = notifier.send_notification(message, event_data)
            
            if result["success"]:
                EventStore.update_event_status(event_id, EventStatus.SUCCESS.value)
                
                # Mark as processed for idempotency
                if idempotency_key:
                    IdempotencyManager.mark_processed(idempotency_key)
                    IdempotencyManager.store_event_id(idempotency_key, event_id)
                
                return {"status": "success", "event_id": event_id}
            else:
                error_msg = result.get("error", "Unknown error")
                EventStore.update_event_status(event_id, EventStatus.FAILED.value, error_msg)
                
                # Retry on failure (if retries available)
                if self.request.retries < self.max_retries:
                    raise self.retry(countdown=60, exc=Exception(error_msg))
                
                return {"status": "failed", "event_id": event_id, "error": error_msg}
        
        else:
            EventStore.update_event_status(
                event_id, 
                EventStatus.FAILED.value, 
                f"Unknown source: {source}"
            )
            return {"status": "failed", "event_id": event_id, "error": "Unknown source"}
    
    except Exception as e:
        # Update retry count
        event = EventStore.get_event(event_id)
        if event:
            event["retry_count"] = event.get("retry_count", 0) + 1
            EventStore.save_event(event)
        
        EventStore.update_event_status(
            event_id, 
            EventStatus.RETRYING.value, 
            str(e)
        )
        
        # Retry with exponential backoff
        raise self.retry(countdown=60 * (2 ** self.request.retries), exc=e)
