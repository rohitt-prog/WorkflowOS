import logging
from typing import List, Optional
from bson import ObjectId
from backend.database import get_database
from backend.models.event import EventCreate, EventResponse

logger = logging.getLogger(__name__)

class EventService:
    def __init__(self):
        pass

    @property
    def collection(self):
        return get_database()["events"]

    async def create_event(self, event_data: EventCreate) -> EventResponse:
        """
        Store an activity event in MongoDB.
        Preserves flexible metadata structure for future pipeline extensions.
        """
        doc = event_data.model_dump()
        result = await self.collection.insert_one(doc)
        event_id = str(result.inserted_id)
        
        logger.info(f"Event created with ID: {event_id} (app: {event_data.application}, type: {event_data.event_type})")
        
        return EventResponse(
            id=event_id,
            session_id=event_data.session_id,
            timestamp=event_data.timestamp,
            application=event_data.application,
            event_type=event_data.event_type,
            target=event_data.target,
            metadata=event_data.metadata or {}
        )

    async def get_events(
        self,
        limit: int = 20,
        session_id: Optional[str] = None,
        application: Optional[str] = None
    ) -> List[EventResponse]:
        """
        Retrieve recent activity events with optional filtering.
        Sorted by timestamp in descending order (most recent first).
        """
        filter_query = {}
        if session_id:
            filter_query["session_id"] = session_id
        if application:
            filter_query["application"] = application

        # Cap limit to reasonable range for performance
        effective_limit = max(1, min(limit, 100))

        cursor = self.collection.find(filter_query).sort("timestamp", -1).limit(effective_limit)
        events = []
        async for doc in cursor:
            events.append(
                EventResponse(
                    id=str(doc["_id"]),
                    session_id=doc.get("session_id", ""),
                    timestamp=str(doc.get("timestamp", "")),
                    application=doc.get("application", ""),
                    event_type=doc.get("event_type", ""),
                    target=doc.get("target"),
                    metadata=doc.get("metadata") or {}
                )
            )
        return events

    async def get_event_by_id(self, event_id: str) -> Optional[EventResponse]:
        """
        Retrieve a single event by its database ID.
        """
        if not ObjectId.is_valid(event_id):
            return None

        doc = await self.collection.find_one({"_id": ObjectId(event_id)})
        if not doc:
            return None

        return EventResponse(
            id=str(doc["_id"]),
            session_id=doc.get("session_id", ""),
            timestamp=str(doc.get("timestamp", "")),
            application=doc.get("application", ""),
            event_type=doc.get("event_type", ""),
            target=doc.get("target"),
            metadata=doc.get("metadata") or {}
        )

    async def delete_all_events(self) -> int:
        """
        Purge all events for development and test reset purposes.
        """
        result = await self.collection.delete_many({})
        logger.info(f"Purged {result.deleted_count} events from database.")
        return result.deleted_count

event_service = EventService()
