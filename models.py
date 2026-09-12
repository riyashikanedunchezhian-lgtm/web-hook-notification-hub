from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Literal
from enum import Enum


class EventStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"


class WebhookEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(datetime.utcnow().timestamp()))
    event_type: str
    source: str  # "github", "stripe", etc.
    payload: dict
    received_at: datetime = Field(default_factory=datetime.utcnow)
    status: EventStatus = EventStatus.PENDING
    retry_count: int = 0
    error_message: Optional[str] = None
    processed_at: Optional[datetime] = None
    idempotency_key: Optional[str] = None


class WebhookResponse(BaseModel):
    success: bool
    message: str
    event_id: Optional[str] = None


class DashboardEvent(BaseModel):
    id: str
    event_type: str
    source: str
    received_at: datetime
    status: EventStatus
    retry_count: int
    error_message: Optional[str] = None
    processed_at: Optional[datetime] = None
