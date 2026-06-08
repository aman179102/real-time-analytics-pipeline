from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from src.api.dependencies import (
    get_analytics_service,
    get_event_processor,
    get_queue_producer,
    require_role,
    verify_token,
)
from src.api.errors import NotFoundError, ValidationError
from src.core.analytics_service import AnalyticsService
from src.core.event_processor import EventProcessor
from src.domain.interfaces import QueueProducerInterface
from src.domain.models import AnalyticsEvent, EventStatus, EventType, UserRole
from src.domain.value_objects import (
    FilterCriteria,
    PaginatedResult,
    PaginationParams,
    TimeRange,
)
from src.infrastructure.logging import get_logger
from src.infrastructure.metrics import metrics

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/events", tags=["Events"])


class EventCreateRequest(BaseModel):
    event_type: str = Field(..., description="Type of event")
    source: str = Field(..., min_length=1, max_length=255)
    payload: dict[str, Any] = Field(default_factory=dict)
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    timestamp: Optional[datetime] = None


class EventResponse(BaseModel):
    event_id: str
    event_type: str
    source: str
    payload: dict[str, Any]
    timestamp: datetime
    user_id: Optional[str]
    session_id: Optional[str]
    status: str


class EventListResponse(BaseModel):
    items: list[EventResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_previous: bool


@router.post("/ingest", response_model=dict, status_code=201)
async def ingest_event(
    request: EventCreateRequest,
    req: Request,
    producer: QueueProducerInterface = Depends(get_queue_producer),
    token: dict = Depends(verify_token),
) -> dict:
    try:
        event_type = EventType(request.event_type)
    except ValueError:
        raise ValidationError(f"Invalid event type: {request.event_type}")

    event = AnalyticsEvent(
        event_type=event_type,
        source=request.source,
        payload=request.payload,
        user_id=request.user_id,
        session_id=request.session_id,
        ip_address=request.ip_address or req.client.host if req.client else None,
        user_agent=request.user_agent or req.headers.get("user-agent"),
        timestamp=request.timestamp or datetime.utcnow(),
    )

    msg_id = await producer.publish(event)

    metrics.increment_counter("events_ingested")
    logger.info("Event ingested: %s type=%s", event.event_id, event.event_type.value)

    return {
        "event_id": event.event_id,
        "message_id": msg_id,
        "status": "accepted",
    }


@router.post("/ingest/batch", status_code=201)
async def ingest_events_batch(
    requests: list[EventCreateRequest],
    req: Request,
    producer: QueueProducerInterface = Depends(get_queue_producer),
    token: dict = Depends(verify_token),
) -> dict:
    events = []
    for r in requests:
        try:
            event_type = EventType(r.event_type)
        except ValueError:
            continue

        event = AnalyticsEvent(
            event_type=event_type,
            source=r.source,
            payload=r.payload,
            user_id=r.user_id,
            session_id=r.session_id,
            ip_address=r.ip_address or (req.client.host if req.client else None),
            user_agent=r.user_agent,
            timestamp=r.timestamp or datetime.utcnow(),
        )
        events.append(event)

    msg_ids = await producer.publish_batch(events)
    metrics.increment_counter("events_ingested_batch", len(events))

    return {
        "count": len(events),
        "event_ids": [e.event_id for e in events],
        "status": "accepted",
    }


@router.get("", response_model=EventListResponse)
async def list_events(
    start: datetime = Query(..., description="Start of time range"),
    end: datetime = Query(..., description="End of time range"),
    event_type: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
    token: dict = Depends(verify_token),
) -> EventListResponse:
    time_range = TimeRange(start=start, end=end)
    pagination = PaginationParams(page=page, page_size=page_size)

    filters = FilterCriteria(
        event_types=[event_type] if event_type else None,
        sources=[source] if source else None,
        user_ids=[user_id] if user_id else None,
        statuses=[status] if status else None,
        search_query=search,
    )

    result = await analytics_service.get_events(time_range, filters, pagination)

    return EventListResponse(
        items=[
            EventResponse(
                event_id=e.event_id,
                event_type=e.event_type.value,
                source=e.source,
                payload=e.payload,
                timestamp=e.timestamp,
                user_id=e.user_id,
                session_id=e.session_id,
                status=e.status.value,
            )
            for e in result.items
        ],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
        total_pages=result.total_pages,
        has_next=result.has_next,
        has_previous=result.has_previous,
    )


@router.get("/{event_id}", response_model=EventResponse)
async def get_event(
    event_id: str,
    analytics_service: AnalyticsService = Depends(get_analytics_service),
    token: dict = Depends(verify_token),
) -> EventResponse:
    event = await analytics_service.get_event_by_id(event_id)
    if not event:
        raise NotFoundError(f"Event {event_id} not found")

    return EventResponse(
        event_id=event.event_id,
        event_type=event.event_type.value,
        source=event.source,
        payload=event.payload,
        timestamp=event.timestamp,
        user_id=event.user_id,
        session_id=event.session_id,
        status=event.status.value,
    )
