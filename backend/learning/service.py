import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Set

from automation.models import AutomationExecution, AutomationStatus
from backend.learning.models import (
    FeedbackDecision,
    RecommendationStatus,
    WorkflowFeedback,
    WorkflowFeedbackRequest,
    WorkflowLearningState,
)
from backend.learning.outcome import (
    interpret_execution_outcome,
    ExecutionLearningOutcome,
    evaluate_execution_outcome,
    WorkflowExecutionOutcome,
    StepOutcome,
    ExecutionOutcomeStatus,
    FailureCategory,
)
from backend.learning.evidence import (
    StrategyOutcomeEvidence,
    ClosedLoopSummary,
    update_strategy_evidence,
    synthesize_closed_loop_summary,
)
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
    if normalized_seq in (
        ["list_recent_messages", "search_customer"],
        ["search_messages", "read_message", "download_attachment", "search_customer", "update_customer", "send_message"],
    ):
        return "wf_gmail_triage_pipeline"

    # Deterministic SHA-256 fingerprint
    digest = hashlib.sha256(seq_key.encode("utf-8")).hexdigest()[:12]
    return f"wf_{digest}"


class LearningService:
    """
    Phase 9 & Phase 11: Learning Service coordinating human feedback persistence,
    execution telemetry learning, deterministic recommendation state tracking,
    and closed-loop strategy outcome evidence for intelligent automation planning.
    """

    def __init__(self):
        # In-memory caches for fast local lookup and test isolation
        self._states: Dict[str, WorkflowLearningState] = {}
        self._feedback_history: Dict[str, List[WorkflowFeedback]] = {}
        # Tracks execution IDs and their processed statuses to guarantee idempotency
        self._processed_executions: Dict[str, Set[str]] = {}
        # Phase 11 Closed-Loop storage
        self._strategy_evidence: Dict[str, StrategyOutcomeEvidence] = {}
        self._execution_outcomes: Dict[str, List[WorkflowExecutionOutcome]] = {}
        # Tracks deleted rejected workflows
        self._deleted_workflows: Set[str] = set()

    def reset_cache(self) -> None:
        """Clears in-memory caches (used between tests)."""
        self._states.clear()
        self._feedback_history.clear()
        self._processed_executions.clear()
        self._strategy_evidence.clear()
        self._execution_outcomes.clear()
        self._deleted_workflows.clear()

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

    async def _persist_strategy_evidence_db(self, evidence: StrategyOutcomeEvidence) -> None:
        """Upserts strategy outcome evidence into 'strategy_outcome_evidence' collection."""
        try:
            from backend.database import get_database
            db = get_database()
            if db is not None:
                doc = evidence.model_dump()
                await db["strategy_outcome_evidence"].update_one(
                    {
                        "workflow_id": evidence.workflow_id,
                        "step_action": evidence.step_action,
                        "strategy": evidence.strategy,
                    },
                    {"$set": doc},
                    upsert=True,
                )
        except Exception as e:
            logger.warning(
                f"[LearningService] MongoDB strategy evidence persistence failed for "
                f"{evidence.workflow_id}:{evidence.step_action}:{evidence.strategy}: {e}. "
                "Evidence remains in local memory."
            )

    async def _persist_execution_outcome_db(self, outcome: WorkflowExecutionOutcome) -> None:
        """Persists workflow execution outcome into 'workflow_execution_outcomes' collection."""
        try:
            from backend.database import get_database
            db = get_database()
            if db is not None:
                doc = outcome.model_dump()
                await db["workflow_execution_outcomes"].update_one(
                    {"execution_id": outcome.execution_id},
                    {"$set": doc},
                    upsert=True,
                )
        except Exception as e:
            logger.warning(
                f"[LearningService] MongoDB execution outcome persistence failed for {outcome.execution_id}: {e}."
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

    # -----------------------------------------------------------------------
    # Phase 11: Closed-Loop Strategy Evidence & Outcomes
    # -----------------------------------------------------------------------

    async def record_closed_loop_outcome(
        self,
        execution: AutomationExecution,
        target_workflow_id: Optional[str] = None,
        step_strategies: Optional[Dict[str, str]] = None,
    ) -> Optional[WorkflowExecutionOutcome]:
        """
        Phase 11: Evaluates an AutomationExecution, records strategy outcome evidence,
        updates closed-loop telemetry across workflow and step levels, and updates
        Phase 9 learning state backward-compatibly.

        Guarantees strict execution-level idempotency: a terminal execution contributes
        to Phase 11 strategy evidence exactly once.
        """
        if execution.status in (AutomationStatus.PENDING, AutomationStatus.RUNNING):
            return None

        exec_id = execution.execution_id
        processed_set = self._processed_executions.setdefault(exec_id, set())
        idempotency_tag = "phase11:evidence_processed"

        # 1. In-memory idempotency check
        if idempotency_tag in processed_set:
            logger.info(f"[LearningService] Execution '{exec_id}' already contributed to Phase 11 evidence. Idempotent return.")
            await self.record_execution_outcome(execution, target_workflow_id=target_workflow_id)
            for out_list in self._execution_outcomes.values():
                for o in out_list:
                    if o.execution_id == exec_id:
                        return o
            return evaluate_execution_outcome(execution, target_workflow_id, step_strategies)

        # 2. MongoDB Atlas idempotency check
        try:
            from backend.database import get_database
            db = get_database()
            if db is not None:
                existing_doc = await db["workflow_execution_outcomes"].find_one({"execution_id": exec_id})
                if existing_doc:
                    processed_set.add(idempotency_tag)
                    logger.info(f"[LearningService] Execution '{exec_id}' already persisted in DB outcomes. Idempotent return.")
                    await self.record_execution_outcome(execution, target_workflow_id=target_workflow_id)
                    existing_doc.pop("_id", None)
                    existing_outcome = WorkflowExecutionOutcome(**existing_doc)
                    out_list = self._execution_outcomes.setdefault(existing_outcome.workflow_id, [])
                    if not any(o.execution_id == exec_id for o in out_list):
                        out_list.append(existing_outcome)
                    return existing_outcome
        except Exception as e:
            logger.warning(f"[LearningService] DB check for execution outcome idempotency failed for {exec_id}: {e}")

        # 3. First-time processing for this terminal execution:
        # 3.1 Update Phase 9 learning state (preserves existing Phase 9 formula and behavior)
        await self.record_execution_outcome(execution, target_workflow_id=target_workflow_id)

        # 3.2 Evaluate execution into structured WorkflowExecutionOutcome
        evaluated = evaluate_execution_outcome(
            execution=execution,
            target_workflow_id=target_workflow_id,
            step_strategies=step_strategies,
        )
        if not evaluated:
            return None

        # 3.3 Store in execution outcomes history
        outcomes_list = self._execution_outcomes.setdefault(evaluated.workflow_id, [])
        existing_idx = next((i for i, o in enumerate(outcomes_list) if o.execution_id == evaluated.execution_id), None)
        if existing_idx is not None:
            outcomes_list[existing_idx] = evaluated
        else:
            outcomes_list.append(evaluated)

        await self._persist_execution_outcome_db(evaluated)

        # 3.4 Update strategy outcome evidence per step (skip unexecuted, paused, or cancelled steps)
        for step in evaluated.step_outcomes:
            if step.status in (
                ExecutionOutcomeStatus.PAUSED,
                ExecutionOutcomeStatus.CANCELLED,
                ExecutionOutcomeStatus.NOT_EXECUTED,
            ):
                continue

            # Fallback learning: if fallback was used, primary strategy failed
            if step.is_fallback and step.primary_strategy and step.primary_strategy.upper() != step.strategy.upper():
                primary_key = f"{evaluated.workflow_id}:{step.action.lower()}:{step.primary_strategy.upper()}"
                primary_curr = self._strategy_evidence.get(primary_key)
                primary_failure_step = StepOutcome(
                    step_id=step.step_id,
                    action=step.action,
                    application=step.application,
                    strategy=step.primary_strategy,
                    status=ExecutionOutcomeStatus.FAILED,
                    duration_seconds=None,
                    retries=0,
                    is_fallback=False,
                    failure_category=step.failure_category or FailureCategory.UNKNOWN,
                    error_message=f"Primary strategy {step.primary_strategy} failed; fallback {step.strategy} executed.",
                )
                updated_primary = update_strategy_evidence(primary_curr, primary_failure_step, evaluated.workflow_id)
                self._strategy_evidence[primary_key] = updated_primary
                await self._persist_strategy_evidence_db(updated_primary)

            # Update evidence for the executed strategy
            key = f"{evaluated.workflow_id}:{step.action.lower()}:{step.strategy.upper()}"
            curr_evidence = self._strategy_evidence.get(key)
            updated_evidence = update_strategy_evidence(curr_evidence, step, evaluated.workflow_id)
            self._strategy_evidence[key] = updated_evidence
            await self._persist_strategy_evidence_db(updated_evidence)

        # Mark as processed in Phase 11 idempotency tracking
        processed_set.add(idempotency_tag)

        logger.info(
            f"[LearningService] Recorded Phase 11 closed-loop outcome for '{evaluated.workflow_id}': "
            f"status={evaluated.status.value}, steps={len(evaluated.step_outcomes)}."
        )
        return evaluated

    async def get_strategy_evidence(
        self,
        workflow_id: str,
        step_action: Optional[str] = None,
        strategy: Optional[str] = None,
    ) -> List[StrategyOutcomeEvidence]:
        """
        Retrieves empirical strategy evidence for a workflow, optionally filtered
        by step_action and strategy.
        """
        try:
            from backend.database import get_database
            db = get_database()
            if db is not None:
                query: Dict[str, Any] = {"workflow_id": workflow_id}
                if step_action:
                    query["step_action"] = step_action.lower()
                if strategy:
                    query["strategy"] = strategy.upper()
                cursor = db["strategy_outcome_evidence"].find(query)
                db_results = []
                async for doc in cursor:
                    doc.pop("_id", None)
                    ev = StrategyOutcomeEvidence(**doc)
                    key = f"{ev.workflow_id}:{ev.step_action.lower()}:{ev.strategy.upper()}"
                    self._strategy_evidence[key] = ev
                    db_results.append(ev)
                if db_results:
                    return db_results
        except Exception as e:
            logger.warning(f"[LearningService] MongoDB fetch failed for strategy evidence of {workflow_id}: {e}")

        # Local in-memory cache lookup
        results: List[StrategyOutcomeEvidence] = []
        prefix = f"{workflow_id}:"
        for key, ev in self._strategy_evidence.items():
            if key.startswith(prefix):
                if step_action and ev.step_action.lower() != step_action.lower():
                    continue
                if strategy and ev.strategy.upper() != strategy.upper():
                    continue
                results.append(ev)

        return results

    async def get_workflow_outcomes(
        self,
        workflow_id: str,
        limit: int = 50,
        skip: int = 0,
    ) -> List[WorkflowExecutionOutcome]:
        """
        Retrieves chronological execution outcomes for a workflow.
        """
        try:
            from backend.database import get_database
            db = get_database()
            if db is not None:
                cursor = (
                    db["workflow_execution_outcomes"]
                    .find({"workflow_id": workflow_id})
                    .sort("started_at", -1)
                    .skip(skip)
                    .limit(limit)
                )
                db_results = []
                async for doc in cursor:
                    doc.pop("_id", None)
                    db_results.append(WorkflowExecutionOutcome(**doc))
                if db_results:
                    return db_results
        except Exception as e:
            logger.warning(f"[LearningService] MongoDB fetch failed for outcomes of {workflow_id}: {e}")

        local = self._execution_outcomes.get(workflow_id, [])
        sorted_local = sorted(local, key=lambda o: o.started_at, reverse=True)
        return sorted_local[skip : skip + limit]

    async def get_closed_loop_summary(
        self,
        workflow_id: str,
        workflow_name: Optional[str] = None,
    ) -> ClosedLoopSummary:
        """
        Synthesizes an executive closed-loop summary combining execution metrics,
        strategy evidence, and deterministic adaptation insights.
        """
        evidence_list = await self.get_strategy_evidence(workflow_id)
        outcomes = await self.get_workflow_outcomes(workflow_id, limit=200)

        # Tally execution counts
        total_execs = len(outcomes)
        succ_execs = sum(1 for o in outcomes if o.status == ExecutionOutcomeStatus.SUCCESS)
        fail_execs = sum(1 for o in outcomes if o.status == ExecutionOutcomeStatus.FAILED)
        part_execs = sum(1 for o in outcomes if o.status == ExecutionOutcomeStatus.PARTIAL)
        canc_execs = sum(1 for o in outcomes if o.status == ExecutionOutcomeStatus.CANCELLED)
        paus_execs = sum(1 for o in outcomes if o.status == ExecutionOutcomeStatus.PAUSED)

        # If no outcomes stored yet, check Phase 9 learning state
        if total_execs == 0:
            state = await self.get_learning_state(workflow_id)
            total_execs = state.execution_count
            succ_execs = state.successful_execution_count
            fail_execs = state.failed_execution_count
            paus_execs = state.intervention_count

        resolved_name = workflow_name or f"Workflow {workflow_id}"
        if resolved_name.startswith("Workflow wf_"):
            if workflow_id == "wf_customer_support_pipeline":
                resolved_name = "Customer Email & Support Pipeline"
            elif workflow_id == "wf_gmail_triage_pipeline":
                resolved_name = "Gmail Triage & Verification Pipeline"

        return synthesize_closed_loop_summary(
            workflow_id=workflow_id,
            workflow_name=resolved_name,
            evidence_list=evidence_list,
            total_execs=total_execs,
            succ_execs=succ_execs,
            fail_execs=fail_execs,
            part_execs=part_execs,
            canc_execs=canc_execs,
            paus_execs=paus_execs,
        )

    # -----------------------------------------------------------------------
    # Rejected Workflow Deletion (UX Improvement 3)
    # -----------------------------------------------------------------------

    async def is_workflow_rejected(self, workflow_id: str) -> bool:
        """
        Determines whether a workflow is currently in an explicitly rejected state.
        A workflow is rejected if its most recent operator review decision was 'reject',
        or if it has rejection feedback records and zero approvals.

        IMPORTANT: A status of DEPRIORITIZED alone does NOT constitute a rejected state
        unless accompanied by an explicit rejection decision.
        """
        if workflow_id in self._deleted_workflows:
            return False

        # Check latest feedback in history
        history = await self.get_feedback_history(workflow_id, limit=1)
        if history and len(history) > 0:
            if history[0].decision == FeedbackDecision.REJECT:
                return True
            if history[0].decision in (FeedbackDecision.APPROVE, FeedbackDecision.EDIT_APPROVE):
                return False

        # Fallback to learning state
        state = await self.get_learning_state(workflow_id)
        if state.last_feedback and isinstance(state.last_feedback, dict):
            decision = state.last_feedback.get("decision")
            if decision == FeedbackDecision.REJECT.value:
                return True
            if decision in (FeedbackDecision.APPROVE.value, FeedbackDecision.EDIT_APPROVE.value):
                return False

        if state.rejection_count > 0 and state.approval_count == 0:
            return True

        return False

    async def delete_rejected_workflow(self, workflow_id: str) -> bool:
        """
        Permanently deletes a rejected workflow candidate from active discovery and learning state.
        Raises ValueError if the workflow is not in an explicitly rejected state.
        """
        if not await self.is_workflow_rejected(workflow_id):
            raise ValueError(
                f"Workflow '{workflow_id}' cannot be deleted because it is not in an explicitly rejected state."
            )

        self._deleted_workflows.add(workflow_id)
        self._states.pop(workflow_id, None)
        self._feedback_history.pop(workflow_id, None)

        now_iso = datetime.now(timezone.utc).isoformat()
        try:
            from backend.database import get_database
            db = get_database()
            if db is not None:
                await db["deleted_workflows"].update_one(
                    {"workflow_id": workflow_id},
                    {"$set": {"workflow_id": workflow_id, "deleted_at": now_iso}},
                    upsert=True,
                )
                await db["workflow_learning_state"].delete_one({"workflow_id": workflow_id})
        except Exception as e:
            logger.warning(
                f"[LearningService] MongoDB persistence failed for workflow deletion of {workflow_id}: {e}. "
                "Tombstone remains in local memory."
            )

        return True

    async def get_deleted_workflow_ids(self) -> Set[str]:
        """
        Retrieves all canonical workflow IDs that have been deleted.
        Synchronizes from MongoDB 'deleted_workflows' collection if available.
        """
        try:
            from backend.database import get_database
            db = get_database()
            if db is not None:
                cursor = db["deleted_workflows"].find({}, {"workflow_id": 1})
                docs = await cursor.to_list(length=2000)
                for doc in docs:
                    wid = doc.get("workflow_id")
                    if wid:
                        self._deleted_workflows.add(wid)
        except Exception as e:
            logger.warning(f"[LearningService] Loading deleted workflows from MongoDB failed: {e}")

        return set(self._deleted_workflows)


# Singleton instance
learning_service = LearningService()
