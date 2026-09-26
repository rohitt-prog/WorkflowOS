from typing import List, Optional
from pydantic import BaseModel, Field

class DiscoveredWorkflow(BaseModel):
    """
    Represents a detected repeated workflow candidate across user sessions.
    """
    label: str = Field(
        default="Repeated Workflow",
        description="Deterministic human-readable label identifying the workflow pattern"
    )
    sequence: List[str] = Field(
        ...,
        description="Normalized ordered list of event_type verbs defining the workflow"
    )
    occurrences: int = Field(
        ...,
        ge=1,
        description="Number of distinct sessions where this workflow sequence was observed"
    )
    similarity: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Average sequence similarity score across matched sessions"
    )
    session_ids: List[str] = Field(
        ...,
        description="List of session IDs that participated in this repeated workflow"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "label": "Customer Request Processing",
                "sequence": [
                    "open_email",
                    "download_attachment",
                    "search_customer",
                    "update_customer",
                    "send_message"
                ],
                "occurrences": 3,
                "similarity": 1.0,
                "session_ids": [
                    "session_001",
                    "session_002",
                    "session_003"
                ]
            }
        }
    }


class DiscoveryResult(BaseModel):
    """
    Output model for GET /api/discovery/repeated
    """
    detected: bool = Field(
        ...,
        description="True if one or more repeated workflows meet discovery criteria"
    )
    workflows: List[DiscoveredWorkflow] = Field(
        default_factory=list,
        description="List of detected repeated workflow candidates"
    )
