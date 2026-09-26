import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from backend.database import get_database

logger = logging.getLogger(__name__)

def parse_iso_timestamp(ts: Union[str, datetime, Any]) -> datetime:
    """
    Safely parses an ISO 8601 timestamp string into a timezone-aware datetime object.
    Falls back to datetime.min if unparseable to ensure consistent sorting.
    """
    if isinstance(ts, datetime):
        if ts.tzinfo is None:
            return ts.replace(tzinfo=timezone.utc)
        return ts
    if isinstance(ts, str):
        try:
            # Handle ISO string with or without trailing 'Z'
            cleaned = ts.replace("Z", "+00:00")
            return datetime.fromisoformat(cleaned)
        except (ValueError, TypeError):
            try:
                # Fallback for common strptime variations
                return datetime.strptime(ts, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            except Exception:
                pass
    return datetime.min.replace(tzinfo=timezone.utc)


def build_session_sequences(events: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """
    Groups events by session_id, orders each session chronologically by timestamp,
    and normalizes the events to ordered lists of event_type verbs.
    
    Ignores MongoDB `_id`, customer names, and dynamic metadata to focus
    strictly on the functional behavioral verb sequence.
    
    Returns:
        Dict[session_id, List[event_type]]
    """
    # Group raw events by session_id
    grouped_events: Dict[str, List[Dict[str, Any]]] = {}
    for ev in events:
        session_id = ev.get("session_id")
        if not session_id:
            continue
        grouped_events.setdefault(session_id, []).append(ev)

    session_sequences: Dict[str, List[str]] = {}
    for session_id, ev_list in grouped_events.items():
        # Chronological sort strictly by parsed timestamp (never by MongoDB _id)
        sorted_events = sorted(
            ev_list,
            key=lambda e: parse_iso_timestamp(e.get("timestamp"))
        )
        # Normalize to list of event_type strings
        normalized_sequence = [
            str(e.get("event_type", "")).strip()
            for e in sorted_events
            if e.get("event_type")
        ]
        if normalized_sequence:
            session_sequences[session_id] = normalized_sequence

    return session_sequences


async def fetch_session_sequences(
    collection=None,
    limit: int = 1000
) -> Dict[str, List[str]]:
    """
    Retrieves events from MongoDB collection, groups them by session,
    and returns chronological normalized event sequences per session.
    """
    if collection is None:
        collection = get_database()["events"]

    # Fetch events ordered by timestamp ascending
    cursor = collection.find({}).sort("timestamp", 1).limit(limit)
    events: List[Dict[str, Any]] = []
    async for doc in cursor:
        events.append(doc)

    logger.debug(f"Retrieved {len(events)} events for sequence building.")
    return build_session_sequences(events)
