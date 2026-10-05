import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, status
from backend.models.event import EventCreate, EventResponse
from backend.services.event_service import event_service
from backend.privacy.service import privacy_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/events", tags=["events"])

@router.post(
    "",
    response_model=EventResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new activity event",
    description="Accepts a structured user activity event, validates fields, and stores it in MongoDB."
)
async def create_event(event_data: EventCreate):
    # Phase 12 Privacy Gate: enforce collection state
    if not privacy_service.is_collection_enabled():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Activity event collection is currently disabled by privacy policy."
        )

    try:
        created = await event_service.create_event(event_data)
        return created
    except Exception as e:
        logger.error("Failed to record event", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record event. Please try again."
        )

@router.get(
    "",
    response_model=List[EventResponse],
    summary="List recent activity events",
    description="Returns recent activity events sorted newest first. Supports filtering by session_id and application."
)
async def get_events(
    limit: int = Query(20, ge=1, le=100, description="Maximum number of events to return"),
    session_id: Optional[str] = Query(None, description="Filter events by session ID"),
    application: Optional[str] = Query(None, description="Filter events by application name")
):
    try:
        events = await event_service.get_events(
            limit=limit,
            session_id=session_id,
            application=application
        )
        return events
    except Exception as e:
        logger.error("Failed to retrieve events", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve events. Please try again."
        )

@router.get(
    "/{event_id}",
    response_model=EventResponse,
    summary="Get single event by ID",
    description="Retrieves a specific event by its MongoDB identifier."
)
async def get_event(event_id: str):
    event = await event_service.get_event_by_id(event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event with id '{event_id}' not found"
        )
    return event

@router.delete(
    "",
    summary="Purge all events (Development / Testing only)",
    description="Clears ALL activity events from the database. For dev/testing environments."
)
async def delete_all_events():
    deleted_count = await event_service.delete_all_events()
    return {"message": "All events cleared", "deleted_count": deleted_count}


@router.delete(
    "/session/{session_id}",
    summary="Delete events for a specific session (Development / Testing only)",
    description=(
        "Removes all events belonging to the given session_id. "
        "Does not affect any other sessions. "
        "Intended for idempotent dev/test re-seeding workflows."
    )
)
async def delete_session_events(session_id: str):
    deleted_count = await event_service.delete_events_by_session(session_id)
    return {
        "message": f"Events for session '{session_id}' cleared",
        "session_id": session_id,
        "deleted_count": deleted_count,
    }
