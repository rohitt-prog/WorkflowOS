from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

class EventCreate(BaseModel):
    """
    Input schema for registering a user activity event.
    Keeps schema flexible to accommodate arbitrary application metadata.
    """
    session_id: str = Field(..., min_length=1, description="Identifier for user's work session")
    timestamp: str = Field(..., min_length=1, description="ISO 8601 formatted timestamp string")
    application: str = Field(..., min_length=1, description="Source application identifier, e.g. demo_email")
    event_type: str = Field(..., min_length=1, description="Action or event type, e.g. open_email")
    target: Optional[str] = Field(None, description="Optional target resource or entity")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Arbitrary custom event metadata")

    model_config = {
        "json_schema_extra": {
            "example": {
                "session_id": "session_001",
                "timestamp": "2026-09-26T10:30:00Z",
                "application": "demo_email",
                "event_type": "open_email",
                "target": "customer_request",
                "metadata": {
                    "customer": "Rahul"
                }
            }
        }
    }


class EventResponse(BaseModel):
    """
    Output schema for an event stored in MongoDB.
    """
    id: str = Field(..., description="Unique database ID (stringified ObjectId)")
    session_id: str
    timestamp: str
    application: str
    event_type: str
    target: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
