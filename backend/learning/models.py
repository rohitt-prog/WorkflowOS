import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class FeedbackDecision(str, Enum):
    """Supported human feedback decisions for Phase 9."""
    APPROVE = "approve"
    REJECT = "reject"
    EDIT_APPROVE = "edit_approve"


class RecommendationStatus(str, Enum):
    """
    Deterministic recommendation status influenced by accumulated learning signals.
    - NEW: Insufficient evidence (no feedback or executions recorded yet).
    - LEARNING: Some feedback/execution evidence exists, but not yet conclusive.
    - RECOMMENDED: Strong positive human approval and successful execution history.
    - DEPRIORITIZED: Repeated rejection or execution failure evidence. Reversible.
    """
    NEW = "NEW"
    LEARNING = "LEARNING"
    RECOMMENDED = "RECOMMENDED"
    DEPRIORITIZED = "DEPRIORITIZED"


def _generate_feedback_id() -> str:
    return f"fb_{uuid.uuid4().hex[:12]}"


def _current_iso_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


class WorkflowFeedback(BaseModel):
    """
    Structured feedback record representing operator review of a workflow.
    Persisted to the 'workflow_feedback' collection in MongoDB Atlas.
    """
    feedback_id: str = Field(
        default_factory=_generate_feedback_id,
        description="Deterministic or unique ID for this feedback record"
    )
    workflow_id: str = Field(
        ...,
        description="Canonical workflow identifier this feedback pertains to"
    )
    decision: FeedbackDecision = Field(
        ...,
        description="Operator decision: 'approve', 'reject', or 'edit_approve'"
    )
    original_workflow: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Original workflow definition or proposal before review"
    )
    edited_workflow: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Edited workflow definition if decision was 'edit_approve'"
    )
    rejection_reason: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Optional human-provided explanation for rejection"
    )
    timestamp: str = Field(
        default_factory=_current_iso_timestamp,
        description="ISO 8601 UTC timestamp of feedback submission"
    )
    session_id: Optional[str] = Field(
        default=None,
        max_length=256,
        description="Optional session context where review occurred"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Optional execution context, client metadata, or tags"
    )


class WorkflowFeedbackRequest(BaseModel):
    """Payload submitted to POST /api/workflows/{workflow_id}/feedback."""
    decision: FeedbackDecision = Field(
        ...,
        description="Operator decision: 'approve', 'reject', or 'edit_approve'"
    )
    rejection_reason: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Explanation when decision is 'reject'"
    )
    original_workflow: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Original workflow representation"
    )
    edited_workflow: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Modified workflow definition if edit_approve"
    )
    session_id: Optional[str] = Field(
        default=None,
        max_length=256,
        description="Optional session context"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Optional contextual metadata"
    )


class WorkflowLearningState(BaseModel):
    """
    Persistent learning state for each workflow.
    Tracks human interactions and execution outcomes to derive a deterministic
    bounded learning score in [0.0, 1.0] and a recommendation status.
    """
    workflow_id: str = Field(
        ...,
        description="Canonical workflow identifier"
    )
    approval_count: int = Field(
        default=0,
        ge=0,
        description="Total times this workflow was approved"
    )
    rejection_count: int = Field(
        default=0,
        ge=0,
        description="Total times this workflow was rejected"
    )
    edit_count: int = Field(
        default=0,
        ge=0,
        description="Total times this workflow was edited and approved"
    )
    execution_count: int = Field(
        default=0,
        ge=0,
        description="Total times this workflow was executed"
    )
    successful_execution_count: int = Field(
        default=0,
        ge=0,
        description="Total times execution succeeded completely"
    )
    failed_execution_count: int = Field(
        default=0,
        ge=0,
        description="Total times execution failed terminally"
    )
    intervention_count: int = Field(
        default=0,
        ge=0,
        description="Total times human intervention was required during execution"
    )
    recovery_count: int = Field(
        default=0,
        ge=0,
        description="Total times system or human successfully recovered from pause/restart"
    )
    last_feedback: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Summary of the most recent human feedback submission"
    )
    last_execution_status: Optional[str] = Field(
        default=None,
        description="Status of the most recent execution (e.g. 'completed', 'paused', 'failed')"
    )
    last_failed_step: Optional[str] = Field(
        default=None,
        description="Name or action verb of the last step that failed, if any"
    )
    last_failure_reason: Optional[str] = Field(
        default=None,
        description="Sanitized reason for the last failure, if any"
    )
    learning_score: float = Field(
        default=0.50,
        ge=0.0,
        le=1.0,
        description="Deterministic bounded learning score in [0.0, 1.0]"
    )
    recommendation_status: RecommendationStatus = Field(
        default=RecommendationStatus.NEW,
        description="Deterministic recommendation state: NEW, LEARNING, RECOMMENDED, or DEPRIORITIZED"
    )
    learning_explanation: str = Field(
        default="New workflow candidate with no prior feedback or execution history.",
        description="Human-readable deterministic explanation of current recommendation and score"
    )
    updated_at: str = Field(
        default_factory=_current_iso_timestamp,
        description="ISO 8601 UTC timestamp of last state update"
    )


class WorkflowFeedbackResponse(BaseModel):
    """Response returned upon feedback submission."""
    success: bool = True
    feedback: WorkflowFeedback
    learning_state: WorkflowLearningState
    message: str = "Feedback recorded and learning state updated."
