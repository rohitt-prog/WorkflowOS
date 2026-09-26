import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from ai.models import (
    WorkflowProposal,
    GenerateWorkflowRequest,
    GenerateWorkflowResponse,
)
from ai.gemini_service import (
    gemini_workflow_service,
    GeminiConfigurationError,
    WorkflowUnderstandingError,
)
from backend.database import get_database

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.post(
    "/workflow/generate",
    response_model=GenerateWorkflowResponse,
    summary="Generate AI Workflow Understanding Proposal",
    description=(
        "Uses Gemini API structured JSON generation to infer workflow name, intent, "
        "trigger, ordered actions, variables, and applications from an observed sequence."
    ),
)
async def generate_workflow_proposal(request: GenerateWorkflowRequest):
    """
    POST /api/ai/workflow/generate

    Analyzes a sequence of user actions from Phase 2 discovery and produces
    a structured WorkflowProposal for human review.
    """
    # 1. Resolve sequence
    sequence = request.sequence
    workflow_obj = request.workflow or {}
    session_ids: List[str] = []

    if not sequence and isinstance(workflow_obj, dict):
        sequence = workflow_obj.get("sequence")
        session_ids = workflow_obj.get("session_ids", [])
    elif isinstance(workflow_obj, dict):
        session_ids = workflow_obj.get("session_ids", [])

    if not sequence:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A non-empty 'sequence' list is required to generate a workflow proposal.",
        )

    # 2. Resolve applications
    applications = list(request.applications or [])
    if not applications and session_ids:
        try:
            db = get_database()
            apps = await db["events"].distinct("application", {"session_id": {"$in": session_ids}})
            if apps:
                applications = [str(a) for a in apps if a]
        except Exception as e:
            logger.warning(f"Could not fetch applications from DB for sessions {session_ids}: {e}")

    # 3. Build context
    context = dict(request.context or {})
    if isinstance(workflow_obj, dict):
        if "label" in workflow_obj and "label" not in context:
            context["label"] = workflow_obj["label"]
        if "occurrences" in workflow_obj and "occurrences" not in context:
            context["occurrences"] = workflow_obj["occurrences"]
        if "similarity" in workflow_obj and "similarity" not in context:
            context["similarity"] = workflow_obj["similarity"]

    # 4. Invoke Gemini workflow understanding service
    try:
        proposal: WorkflowProposal = gemini_workflow_service.generate_workflow(
            sequence=sequence,
            applications=applications if applications else None,
            context=context if context else None,
        )
        return GenerateWorkflowResponse(
            success=True,
            workflow=proposal,
            error=None,
        )
    except GeminiConfigurationError as ce:
        logger.error(f"Gemini configuration error: {ce}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gemini service is not configured. Missing or invalid GEMINI_API_KEY.",
        )
    except WorkflowUnderstandingError as we:
        logger.error(f"Workflow understanding error: {we}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI workflow understanding failed: {str(we)}",
        )
    except Exception as e:
        logger.error(f"Unexpected error in generate_workflow_proposal: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while understanding the workflow.",
        )
