import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, status
from discovery.models import DiscoveryResult
from discovery.service import discovery_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/discovery", tags=["discovery"])

@router.get(
    "/repeated",
    response_model=DiscoveryResult,
    summary="Detect repeated workflow sequences",
    description=(
        "Analyzes recorded activity events across user sessions, builds ordered sequences, "
        "and applies the deterministic repetition detector to identify repeated workflows."
    )
)
async def get_repeated_workflows(
    min_length: int = Query(
        3,
        ge=1,
        description="Minimum sequence length to qualify as a workflow"
    ),
    min_occurrences: int = Query(
        2,
        ge=2,
        description="Minimum distinct session occurrences to qualify as repeated"
    ),
    similarity_threshold: float = Query(
        0.8,
        ge=0.0,
        le=1.0,
        description="Minimum sequence similarity ratio (0.0 - 1.0)"
    ),
    min_confidence: Optional[float] = Query(
        None,
        ge=0.0,
        le=1.0,
        description="Optional minimum confidence score threshold (0.0 - 1.0)"
    ),
):
    """
    Endpoint for Phase 8.1 deterministic workflow discovery with confidence scoring.
    Retrieves events grouped by session, determines recurring patterns,
    and returns discovered workflow definitions with occurrences, similarity scores,
    and calibrated confidence breakdowns.
    """
    try:
        result = await discovery_service.get_repeated_workflows(
            min_length=min_length,
            min_occurrences=min_occurrences,
            similarity_threshold=similarity_threshold,
            min_confidence=min_confidence,
        )
        return result
    except Exception as e:
        logger.error(f"Failed to detect repeated workflows: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to detect repeated workflows: {str(e)}"
        )
