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
        collection=None
    ) -> DiscoveryResult:
        """
        Retrieves event history from MongoDB, builds ordered session sequences,
        and applies the deterministic repetition detector.
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
                similarity_threshold=similarity_threshold
            )
            return result
        except Exception as e:
            logger.error(f"Error during workflow discovery: {e}", exc_info=True)
            raise e

discovery_service = DiscoveryService()
