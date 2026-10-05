import logging
from typing import Optional
from discovery.sequence import fetch_session_sequences
from discovery.detector import detect_repeated_workflows
from discovery.models import DiscoveryResult

logger = logging.getLogger(__name__)

class DiscoveryService:
    """
    Coordinates event sequence extraction and repetition detection.
    """

    async def get_repeated_workflows(
        self,
        min_length: int = 3,
        min_occurrences: int = 2,
        similarity_threshold: float = 0.8,
        min_confidence: Optional[float] = None,
        min_ranking_score: Optional[float] = None,
        filter_noise: bool = False,
        include_suppressed: bool = False,
        collection=None
    ) -> DiscoveryResult:
        """
        Retrieves event history from MongoDB, builds ordered session sequences,
        and applies the deterministic repetition detector with Phase 8.3 ranking.
        """
        try:
            # Step 1: Retrieve and group chronological sequences by session
            session_sequences = await fetch_session_sequences(collection=collection)
            logger.info(
                f"Built sequences for {len(session_sequences)} sessions. "
                f"Running repetition detector..."
            )

            # Step 2: Run deterministic detection
            result = detect_repeated_workflows(
                session_sequences=session_sequences,
                min_length=min_length,
                min_occurrences=min_occurrences,
                similarity_threshold=similarity_threshold,
                min_confidence=min_confidence,
                min_ranking_score=min_ranking_score,
                filter_noise=filter_noise,
                include_suppressed=include_suppressed,
            )

            # Step 3: Phase 9 Adaptive Learning integration
            try:
                from backend.learning.service import learning_service, derive_workflow_id_from_sequence
                for wf in result.workflows:
                    wf_id = derive_workflow_id_from_sequence(wf.sequence, wf.label)
                    wf.workflow_id = wf_id
                    state = await learning_service.get_learning_state(wf_id)
                    wf.learning_score = state.learning_score
                    wf.recommendation_status = state.recommendation_status.value
                    wf.learning_explanation = state.learning_explanation

                for wf in result.suppressed_workflows:
                    wf_id = derive_workflow_id_from_sequence(wf.sequence, wf.label)
                    wf.workflow_id = wf_id
                    state = await learning_service.get_learning_state(wf_id)
                    wf.learning_score = state.learning_score
                    wf.recommendation_status = state.recommendation_status.value
                    wf.learning_explanation = state.learning_explanation
            except Exception as le:
                logger.warning(f"Could not attach learning signals to discovered workflows: {le}")

            return result
        except Exception as e:
            logger.error(f"Error during workflow discovery: {e}", exc_info=True)
            raise e

discovery_service = DiscoveryService()
