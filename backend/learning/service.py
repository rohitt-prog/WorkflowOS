import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Set

from automation.models import AutomationExecution
from backend.learning.models import (
    FeedbackDecision,
    RecommendationStatus,
    WorkflowFeedback,
    WorkflowFeedbackRequest,
    WorkflowLearningState,
)
from backend.learning.outcome import interpret_execution_outcome, ExecutionLearningOutcome
from backend.learning.state import recalculate_learning_state

logger = logging.getLogger(__name__)


def derive_workflow_id_from_sequence(sequence: List[str], label: Optional[str] = None) -> str:
    """
    Deterministically computes a canonical workflow ID from an action sequence.
    Known canonical templates are mapped to their canonical IDs.
    """
    normalized_seq = [s.strip().lower() for s in sequence if s and s.strip()]
    seq_key = "->".join(normalized_seq)

    # Check known built-in templates
    if normalized_seq == [
        "open_email",
        "download_attachment",
        "search_customer",
        "update_customer",
        "send_message",
    ]:
        return "wf_customer_support_pipeline"
    if normalized_seq == ["list_recent_messages", "search_customer"]:
        return "wf_gmail_triage_pipeline"

    # Deterministic SHA-256 fingerprint
    digest = hashlib.sha256(seq_key.encode("utf-8")).hexdigest()[:12]
    return f"wf_{digest}"


class LearningService:
    """
    Phase 9: Learning Service coordinating human feedback persistence,
    execution telemetry learning, and deterministic recommendation state tracking.
    """

    def __init__(self):
        # In-memory caches for fast local lookup and test isolation
        self._states: Dict[str, WorkflowLearningState] = {}
        self._feedback_history: Dict[str, List[WorkflowFeedback]] = {}
        # Tracks execution IDs and their processed statuses to guarantee idempotency
        self._processed_executions: Dict[str, Set[str]] = {}

    def reset_cache(self) -> None:
        """Clears in-memory caches (used between tests)."""
        self._states.clear()
        self._feedback_history.clear()
        self._processed_executions.clear()

    # -----------------------------------------------------------------------
    # Database Persistence Helpers
    # -----------------------------------------------------------------------

    async def _persist_feedback_db(self, feedback: WorkflowFeedback) -> None:
        """Persists a feedback document to the 'workflow_feedback' collection in MongoDB."""
        try:
            from backend.database import get_database
            db = get_database()
            if db is not None:
                doc = feedback.model_dump()
                await db["workflow_feedback"].insert_one(doc)
        except Exception as e:
            logger.warning(
                f"[LearningService] MongoDB feedback persistence failed for {feedback.feedback_id}: {e}. "
                "Feedback remains in local memory."
            )

    async def _persist_state_db(self, state: WorkflowLearningState) -> None:
        """Upserts the workflow learning state in 'workflow_learning_state' collection."""
        try:
            from backend.database import get_database
            db = get_database()
            if db is not None:
                doc = state.model_dump()
                await db["workflow_learning_state"].update_one(
                    {"workflow_id": state.workflow_id},
                    {"$set": doc},
                    upsert=True,
                )
        except Exception as e:
            logger.warning(
                f"[LearningService] MongoDB learning state persistence failed for {state.workflow_id}: {e}. "
                "State remains in local memory."
            )

    # -----------------------------------------------------------------------
    # State Retrieval & Initialisation
    # -----------------------------------------------------------------------

    async def get_learning_state(self, workflow_id: str) -> WorkflowLearningState:
        """
        Retrieves the persistent learning state for a workflow.
        Returns a fresh state with status=NEW if no history exists.
        """
        if workflow_id in self._states:
            return self._states[workflow_id]

        try:
            from backend.database import get_database
            db = get_database()
            if db is not None:
                doc = await db["workflow_learning_state"].find_one({"workflow_id": workflow_id})
                if doc:
                    doc.pop("_id", None)
                    state = WorkflowLearningState(**doc)
                    self._states[workflow_id] = state
                    return state
        except Exception as e:
            logger.warning(f"[LearningService] Failed fetching state from MongoDB for {workflow_id}: {e}")

        # Return clean NEW state
        fresh_state = WorkflowLearningState(workflow_id=workflow_id)
        self._states[workflow_id] = fresh_state
        return fresh_state

    def get_learning_state_sync(self, workflow_id: str) -> WorkflowLearningState:
        """Synchronous in-memory lookup for learning state."""
        if workflow_id in self._states:
            return self._states[workflow_id]
        fresh_state = WorkflowLearningState(workflow_id=workflow_id)
        self._states[workflow_id] = fresh_state
        return fresh_state

    # -----------------------------------------------------------------------
    # Human Feedback Management
    # -----------------------------------------------------------------------

    async def record_feedback(
        self,
        workflow_id: str,
        request: WorkflowFeedbackRequest,
    ) -> Tuple[WorkflowFeedback, WorkflowLearningState]:
        """
        Records human review feedback, updates deterministic counters, recalculates
        learning score and recommendation status, and persists both feedback and state.
        
        Supported decisions:
        - 'approve': increments approval_count
        - 'reject': increments rejection_count, records rejection_reason
        - 'edit_approve': increments edit_count, records edited_workflow
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        feedback = WorkflowFeedback(
            workflow_id=workflow_id,
            decision=request.decision,
            original_workflow=request.original_workflow,
            edited_workflow=request.edited_workflow,
            rejection_reason=request.rejection_reason,
            session_id=request.session_id,
            metadata=request.metadata or {},
            timestamp=now_iso,
        )

        # 1. Update in-memory feedback history
        if workflow_id not in self._feedback_history:
            self._feedback_history[workflow_id] = []
        self._feedback_history[workflow_id].append(feedback)

        # 2. Persist feedback to MongoDB Atlas
        await self._persist_feedback_db(feedback)

        # 3. Retrieve current state and update counters
        current_state = await self.get_learning_state(workflow_id)
        approvals = current_state.approval_count
        rejections = current_state.rejection_count
        edits = current_state.edit_count

        if request.decision == FeedbackDecision.APPROVE:
            approvals += 1
        elif request.decision == FeedbackDecision.REJECT:
            rejections += 1
        elif request.decision == FeedbackDecision.EDIT_APPROVE:
            edits += 1

        updated_state = current_state.model_copy(update={
            "approval_count": approvals,
            "rejection_count": rejections,
            "edit_count": edits,
            "last_feedback": {
                "feedback_id": feedback.feedback_id,
                "decision": feedback.decision.value,
                "timestamp": feedback.timestamp,
                "rejection_reason": feedback.rejection_reason,
            },
        })

        # 4. Recalculate score and status
        updated_state = recalculate_learning_state(
            updated_state,
            last_rejection_reason=request.rejection_reason,
        )

        # 5. Persist updated state
        self._states[workflow_id] = updated_state
        await self._persist_state_db(updated_state)

        logger.info(
            f"[LearningService] Recorded '{feedback.decision.value}' feedback for '{workflow_id}'. "
            f"New state: score={updated_state.learning_score:.2f}, status={updated_state.recommendation_status.value}."
        )
        return feedback, updated_state

    async def get_feedback_history(
        self,
        workflow_id: str,
        limit: int = 50,
        skip: int = 0,
    ) -> List[WorkflowFeedback]:
        """
        Retrieves chronological feedback history for a workflow.
        """
        results: List[WorkflowFeedback] = []
        try:
            from backend.database import get_database
            db = get_database()
            if db is not None:
                cursor = (
                    db["workflow_feedback"]
                    .find({"workflow_id": workflow_id})
                    .sort("timestamp", -1)
                    .skip(skip)
                    .limit(limit)
                )
                async for doc in cursor:
                    doc.pop("_id", None)
                    results.append(WorkflowFeedback(**doc))
                if results:
                    return results
        except Exception as e:
            logger.warning(f"[LearningService] DB fetch failed for feedback history of {workflow_id}: {e}")

        # Fallback to local memory cache
        local = self._feedback_history.get(workflow_id, [])
        sorted_local = sorted(local, key=lambda f: f.timestamp, reverse=True)
        return sorted_local[skip : skip + limit]

    # -----------------------------------------------------------------------
    # Execution Outcome Learning
    # -----------------------------------------------------------------------

    async def record_execution_outcome(
        self,
        execution: AutomationExecution,
        target_workflow_id: Optional[str] = None,
    ) -> Optional[WorkflowLearningState]:
        """
        Interprets an AutomationExecution run, updates execution telemetry counters,
        recalculates learning score and recommendation status, and persists the state.
        
        Guarantees idempotency so the same execution status transition is not
        counted multiple times.
        """
        outcome = interpret_execution_outcome(execution, target_workflow_id=target_workflow_id)
        if not outcome:
            return None

        # Check idempotency per execution ID and lifecycle status
        status_key = f"{outcome.status}:{outcome.failed_step or ''}:{outcome.is_recovery}"
        processed_set = self._processed_executions.setdefault(outcome.execution_id, set())
        if status_key in processed_set:
            return self._states.get(outcome.workflow_id)

        processed_set.add(status_key)

        workflow_id = outcome.workflow_id
        current_state = await self.get_learning_state(workflow_id)

        # Count total execution once per execution run
        already_counted_run = any(
            k.startswith("completed") or k.startswith("failed") or k.startswith("paused")
            for k in processed_set if k != status_key
        )
        new_execution_count = current_state.execution_count + (0 if already_counted_run else 1)

        succ_count = current_state.successful_execution_count + (1 if outcome.is_completed else 0)
        fail_count = current_state.failed_execution_count + (1 if outcome.is_failed else 0)
        interv_count = current_state.intervention_count + (1 if outcome.requires_intervention else 0)
        recov_count = current_state.recovery_count + (1 if outcome.is_recovery and outcome.is_completed else 0)

        updated_state = current_state.model_copy(update={
            "execution_count": new_execution_count,
            "successful_execution_count": succ_count,
            "failed_execution_count": fail_count,
            "intervention_count": interv_count,
            "recovery_count": recov_count,
            "last_execution_status": outcome.status,
            "last_failed_step": outcome.failed_step or current_state.last_failed_step,
            "last_failure_reason": outcome.failure_reason or current_state.last_failure_reason,
        })

        # Recalculate score and recommendation
        updated_state = recalculate_learning_state(updated_state)

        self._states[workflow_id] = updated_state
        await self._persist_state_db(updated_state)

        logger.info(
            f"[LearningService] Recorded execution outcome '{outcome.status}' for '{workflow_id}'. "
            f"Score: {updated_state.learning_score:.2f}, Status: {updated_state.recommendation_status.value}."
        )
        return updated_state


# Singleton instance
learning_service = LearningService()
