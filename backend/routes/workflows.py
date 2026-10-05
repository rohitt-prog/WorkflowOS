import logging
import re
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, status

from backend.learning.models import (
    WorkflowFeedbackRequest,
    WorkflowFeedbackResponse,
    WorkflowFeedback,
    WorkflowLearningState,
)
from backend.learning.service import learning_service

logger = logging.getLogger(__name__)

# Pre-compiled pattern for workflow_id character-set validation
_WORKFLOW_ID_RE = re.compile(r"[a-zA-Z0-9_\-\.]+")

router = APIRouter(prefix="/api/workflows", tags=["workflows", "learning"])



@router.post(
    "/{workflow_id}/feedback",
    response_model=WorkflowFeedbackResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit Human Review Feedback",
    description=(
        "Phase 9: Records human feedback (approve, reject, edit_approve) for a workflow. "
        "Persists the feedback, recalculates the bounded learning score and recommendation status, "
        "and returns updated learning state. Does NOT trigger autonomous execution."
    ),
)
async def submit_workflow_feedback_endpoint(
    workflow_id: str,
    request: WorkflowFeedbackRequest,
):
    """
    POST /api/workflows/{workflow_id}/feedback
    """
    if not workflow_id or not workflow_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A non-empty workflow_id is required.",
        )
    _wid = workflow_id.strip()
    if len(_wid) > 128:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="workflow_id must not exceed 128 characters.",
        )
    if not _WORKFLOW_ID_RE.fullmatch(_wid):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="workflow_id contains invalid characters. Use only letters, digits, underscores, hyphens, and dots.",
        )

    try:
        feedback, updated_state = await learning_service.record_feedback(
            workflow_id=_wid,
            request=request,
        )
        return WorkflowFeedbackResponse(
            success=True,
            feedback=feedback,
            learning_state=updated_state,
            message="Feedback successfully recorded and learning state updated.",
        )
    except Exception as e:
        logger.error(f"Error submitting feedback for workflow {workflow_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record feedback. Please try again.",
        )


@router.get(
    "/{workflow_id}/feedback",
    response_model=List[WorkflowFeedback],
    summary="Get Feedback History",
    description="Returns chronological audit history of human review decisions for a workflow.",
)
async def get_feedback_history_endpoint(
    workflow_id: str,
    limit: int = Query(50, ge=1, le=200, description="Max feedback records to return"),
    skip: int = Query(0, ge=0, description="Records to skip for pagination"),
):
    """
    GET /api/workflows/{workflow_id}/feedback
    """
    if not workflow_id or not workflow_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A non-empty workflow_id is required.",
        )
    _wid = workflow_id.strip()
    if len(_wid) > 128:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="workflow_id must not exceed 128 characters.",
        )
    if not _WORKFLOW_ID_RE.fullmatch(_wid):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="workflow_id contains invalid characters. Use only letters, digits, underscores, hyphens, and dots.",
        )
    try:
        return await learning_service.get_feedback_history(
            workflow_id=_wid,
            limit=limit,
            skip=skip,
        )
    except Exception as e:
        logger.error(f"Error retrieving feedback history for {workflow_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve feedback history. Please try again.",
        )


@router.get(
    "/{workflow_id}/learning",
    response_model=WorkflowLearningState,
    summary="Get Workflow Learning State",
    description=(
        "Returns the persistent learning state, telemetry counters, bounded learning score, "
        "recommendation status (NEW, LEARNING, RECOMMENDED, DEPRIORITIZED), and deterministic explanation."
    ),
)
async def get_workflow_learning_endpoint(workflow_id: str):
    """
    GET /api/workflows/{workflow_id}/learning
    """
    if not workflow_id or not workflow_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A non-empty workflow_id is required.",
        )
    _wid = workflow_id.strip()
    if len(_wid) > 128:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="workflow_id must not exceed 128 characters.",
        )
    if not _WORKFLOW_ID_RE.fullmatch(_wid):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="workflow_id contains invalid characters. Use only letters, digits, underscores, hyphens, and dots.",
        )

    try:
        state = await learning_service.get_learning_state(_wid)
        return state
    except Exception as e:
        logger.error(f"Error retrieving learning state for {workflow_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve learning state. Please try again.",
        )
