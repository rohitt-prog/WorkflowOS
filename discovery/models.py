from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from discovery.confidence import ConfidenceBreakdown
from discovery.ranking import RankingBreakdown
from discovery.explanation import WorkflowExplanation

class DiscoveredWorkflow(BaseModel):
    """
    Represents a detected repeated workflow candidate across user sessions.
    Enhanced in Phase 8.3 with pattern ranking, noise filtering, and duplicate tracking.
    Enhanced in Phase 8.4 with structured, evidence-grounded explainability.
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
    confidence: float = Field(
        default=0.80,
        ge=0.0,
        le=1.0,
        description="Deterministic composite confidence score (0.0 - 1.0) indicating pattern strength"
    )
    confidence_tier: Optional[str] = Field(
        default=None,
        description="Human-readable confidence tier: 'high', 'medium', or 'low'"
    )
    confidence_breakdown: Optional[ConfidenceBreakdown] = Field(
        default=None,
        description="Detailed signal breakdown contributing to the confidence score"
    )
    confidence_explanation: Optional[str] = Field(
        default=None,
        description="Deterministic explanation of why this confidence score was assigned"
    )

    # Phase 8.3 Ranking & Duplicate Detection fields
    rank: Optional[int] = Field(
        default=None,
        ge=1,
        description="Deterministic 1-based rank among discovered patterns ordered by usefulness"
    )
    ranking_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Deterministic composite utility score (0.0 - 1.0) evaluating automation value"
    )
    quality_tier: Optional[str] = Field(
        default=None,
        description="Human-readable quality tier: 'exceptional', 'strong', 'moderate', or 'low'"
    )
    ranking_breakdown: Optional[RankingBreakdown] = Field(
        default=None,
        description="Detailed breakdown of signals contributing to the ranking score"
    )
    ranking_explanation: Optional[str] = Field(
        default=None,
        description="Deterministic explanation of why this rank and score was assigned"
    )
    is_duplicate: bool = Field(
        default=False,
        description="True if this candidate was identified as a duplicate or shadow of another workflow"
    )
    representative_pattern_id: Optional[str] = Field(
        default=None,
        description="Label or identifier of the primary representative pattern if suppressed as duplicate/shadow"
    )
    suppression_reason: Optional[str] = Field(
        default=None,
        description="Reason for filtering or suppression: MONOTONOUS_REPETITION, OVERLAPPING_SHADOW, EXACT_DUPLICATE, etc."
    )

    # Phase 8.4 Explainability fields
    explanation: Optional[WorkflowExplanation] = Field(
        default=None,
        description="Structured deterministic explainability metadata grounded in observed evidence"
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
                ],
                "rank": 1,
                "ranking_score": 0.88,
                "quality_tier": "exceptional",
                "is_duplicate": False,
                "explanation": {
                    "summary": "Ranked #1 · 5-step workflow with 88/100 exceptional quality across 3 sessions (89% confidence).",
                    "detection_reason": "Qualified as a repeated workflow across 3 distinct sessions with identical execution.",
                    "supporting_sessions": ["session_001", "session_002", "session_003"]
                }
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
        description="List of active detected repeated workflow candidates, ordered by rank"
    )
    suppressed_workflows: List[DiscoveredWorkflow] = Field(
        default_factory=list,
        description="List of filtered noise and duplicate candidates preserved for full auditability"
    )
    total_candidates_evaluated: int = Field(
        default=0,
        description="Total candidates evaluated before noise reduction and deduplication"
    )

