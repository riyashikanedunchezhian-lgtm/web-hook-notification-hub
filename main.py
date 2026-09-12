from fastapi import FastAPI, Request, HTTPException, BackgroundTasks, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from typing import Optional
import json
from datetime import datetime
import uuid

from config import settings
from models import WebhookEvent, WebhookResponse, DashboardEvent, EventStatus
from webhook_security import verify_webhook_signature
from redis_queue import EventStore, IdempotencyManager, celery_app
from tasks import process_webhook
from notifications import GitHubEventHandler


app = FastAPI(title="Webhook Notification Hub", version="1.0.0")

# Templates for dashboard
templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard showing webhook event history."""
    recent_events = EventStore.get_recent_events(limit=50)
    
    # Convert to DashboardEvent models
    dashboard_events = []
    for event in recent_events:
        try:
            dashboard_events.append(DashboardEvent(**event))
        except Exception:
            pass
    
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "events": dashboard_events,
            "total_events": len(dashboard_events)
        }
    )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        from redis_queue import redis_client
        redis_client.ping()
        return {"status": "healthy", "redis": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


@app.post("/webhook/github", response_model=WebhookResponse)
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    verified_payload: bytes = Depends(verify_webhook_signature)
):
    """
    GitHub webhook endpoint.
    
    This endpoint:
    1. Verifies the webhook signature (security)
    2. Extracts idempotency key from headers
    3. Checks for duplicate events
    4. Queues the event for processing
    5. Returns immediately (async processing)
    """
    
    try:
        # Parse payload
        payload = json.loads(verified_payload.decode())
        
        # Extract GitHub headers for idempotency
        github_delivery_id = request.headers.get("X-GitHub-Delivery")
        github_event_type = request.headers.get("X-GitHub-Event", "unknown")
        
        # Create idempotency key
        idempotency_key = f"github:{github_delivery_id}" if github_delivery_id else None
        
        # Check for duplicate
        if idempotency_key and IdempotencyManager.is_duplicate(idempotency_key):
            existing_event_id = IdempotencyManager.get_event_id(idempotency_key)
            return WebhookResponse(
                success=True,
                message="Duplicate event, already processed",
                event_id=existing_event_id
            )
        
        # Create event record
        event = WebhookEvent(
            event_type=github_event_type,
            source="github",
            payload=payload,
            idempotency_key=idempotency_key
        )
        
        # Save to event store
        event_dict = event.model_dump()
        event_dict["received_at"] = event.received_at.isoformat()
        event_dict["status"] = event.status.value
        EventStore.save_event(event_dict)
        
        # Queue for async processing with Celery
        process_webhook.delay(event.id, event_dict)
        
        return WebhookResponse(
            success=True,
            message="Webhook received and queued for processing",
            event_id=event.id
        )
    
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@app.get("/api/events")
async def get_events(limit: int = 50):
    """API endpoint to get recent events."""
    events = EventStore.get_recent_events(limit=limit)
    return {"events": events, "count": len(events)}


@app.get("/api/events/{event_id}")
async def get_event(event_id: str):
    """API endpoint to get a specific event."""
    event = EventStore.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@app.post("/api/events/{event_id}/retry")
async def retry_event(event_id: str):
    """Manually retry a failed event."""
    event = EventStore.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    if event["status"] not in [EventStatus.FAILED.value, EventStatus.RETRYING.value]:
        raise HTTPException(
            status_code=400, 
            detail="Only failed or retrying events can be retried"
        )
    
    # Reset status and queue for processing
    event["status"] = EventStatus.PENDING.value
    event["retry_count"] = event.get("retry_count", 0) + 1
    EventStore.save_event(event)
    
    # Queue for processing
    celery_app.send_task(
        'tasks.process_webhook',
        args=[event_id, event]
    )
    
    return {"success": True, "message": "Event queued for retry"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )
