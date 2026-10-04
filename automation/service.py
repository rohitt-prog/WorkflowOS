import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from ai.models import WorkflowProposal
from automation.models import (
    AutomationExecution,
    AutomationStatus,
    WorkflowDefinition,
    WorkflowStep,
    WorkflowInputDefinition,
    WorkflowTriggerConfig,
    StepCondition,
    RetryPolicy,
    is_valid_transition,
    compute_workflow_definition_hash,
)
from automation.engine import automation_engine, AutomationEngine, InvalidStateTransitionError
from automation.executor import ActionExecutor
from integrations.credentials import sanitize_credential_dict, sanitize_log_message

logger = logging.getLogger(__name__)


class AutomationService:
    """
    Internal service layer managing workflow automation executions, definitions, and history.

    Phase 7.4 adds:
    - Durable persistence in MongoDB Atlas executions collection with memory fallback
    - Safe startup recovery of interrupted executions (RUNNING -> PAUSED with step preservation)
    - Idempotency key deduplication
    - Cryptographic definition hash validation
    - Seamless progress callbacks on each step execution
    """

    def __init__(self, engine: Optional[AutomationEngine] = None):
        self._engine = engine or automation_engine
        self._executions: Dict[str, AutomationExecution] = {}
        self._workflows: Dict[str, WorkflowDefinition] = {}
        self._init_built_in_workflows()

    async def _persist_execution(self, execution: AutomationExecution) -> None:
        """Persists the execution record to MongoDB Atlas durably with credential redaction."""
        try:
            from backend.database import get_database
            db = get_database()
            if db is not None:
                doc = execution.model_dump()
                sanitized_doc = sanitize_credential_dict(doc)
                await db["executions"].update_one(
                    {"execution_id": execution.execution_id},
                    {"$set": sanitized_doc},
                    upsert=True,
                )
        except Exception as e:
            logger.warning(
                f"[AutomationService] MongoDB execution persistence failed for {execution.execution_id}: {e}. "
                "Execution remains available in memory cache."
            )

    async def _on_progress_update(self, execution: AutomationExecution) -> None:
        """Invoked by engine on step progression for durable intermediate status."""
        self._executions[execution.execution_id] = execution
        await self._persist_execution(execution)

    async def load_executions_from_db(self) -> int:
        """Loads historical executions from MongoDB Atlas into in-memory cache."""
        try:
            from backend.database import get_database
            db = get_database()
            if db is not None:
                cursor = db["executions"].find({})
                count = 0
                async for doc in cursor:
                    doc.pop("_id", None)
                    try:
                        exec_obj = AutomationExecution(**doc)
                        self._executions[exec_obj.execution_id] = exec_obj
                        count += 1
                    except Exception as parse_err:
                        logger.warning(f"[AutomationService] Failed parsing execution doc: {parse_err}")
                logger.info(f"[AutomationService] Restored {count} executions from MongoDB Atlas.")
                return count
        except Exception as e:
            logger.warning(f"[AutomationService] MongoDB load failed: {e}. Starting with memory executions.")
        return 0

    async def recover_interrupted_executions(self) -> List[str]:
        """
        Phase 7.4: Safely recovers executions left in RUNNING state due to unexpected shutdown.
        - Identifies active runs and transitions them to PAUSED.
        - Sets requires_human_intervention=True and resume_available=True.
        - Never blindly reruns completed actions; keeps existing completed steps intact.
        - Records recovery decisions and reasons in execution logs and audit fields.
        """
        recovered_ids: List[str] = []
        for exec_id, execution in list(self._executions.items()):
            if execution.status == AutomationStatus.RUNNING:
                logger.warning(
                    f"[AutomationService] Interrupted RUNNING execution detected: '{exec_id}'. "
                    f"Safely recovering to PAUSED (completed {len(execution.completed_actions)}/{execution.total_actions} actions)."
                )
                now_iso = datetime.now(timezone.utc).isoformat()
                recovery_reason = (
                    "Execution interrupted by unexpected server restart or shutdown. "
                    "Completed steps safely preserved; awaiting human review to resume."
                )
                updated_logs = list(execution.execution_logs or [])
                updated_logs.append(f"Recovery: {recovery_reason}")

                recovered = execution.model_copy(update={
                    "status": AutomationStatus.PAUSED,
                    "requires_human_intervention": True,
                    "resume_available": True,
                    "recovery_attempts": (execution.recovery_attempts or 0) + 1,
                    "recovery_reason": recovery_reason,
                    "paused_at": now_iso,
                    "execution_logs": updated_logs,
                    "error": execution.error or "Interrupted by system restart",
                })
                self._executions[exec_id] = recovered
                await self._persist_execution(recovered)
                recovered_ids.append(exec_id)
        return recovered_ids

    def find_by_idempotency_key(self, idempotency_key: str) -> Optional[AutomationExecution]:
        """Looks up an execution by its client idempotency key."""
        if not idempotency_key:
            return None
        for execution in self._executions.values():
            if execution.idempotency_key == idempotency_key:
                return execution
        return None

    def _init_built_in_workflows(self):
        """Seed default declarative workflow templates for Phase 6."""
        now_iso = datetime.now(timezone.utc).isoformat()
        template1 = WorkflowDefinition(
            id="wf_customer_support_pipeline",
            name="Customer Email & Support Pipeline",
            description="Extracts support inquiry, searches CRM, updates record, and sends customer acknowledgement.",
            version="1.0.0",
            trigger=WorkflowTriggerConfig(
                type="event",
                application="demo_email",
                event_type="open_email",
                description="Triggers when a customer support email is opened"
            ),
            inputs=[
                WorkflowInputDefinition(
                    name="customer_name",
                    type="string",
                    default="Rahul Sharma",
                    required=True,
                    description="Full name of customer"
                ),
                WorkflowInputDefinition(
                    name="inquiry_type",
                    type="string",
                    default="support_request",
                    required=False,
                    description="Category of inquiry"
                ),
            ],
            variables={
                "status": "initial",
                "priority": "normal",
            },
            steps=[
                WorkflowStep(
                    id="step_open_email",
                    name="Open Customer Email",
                    type="open_email",
                    application="demo_email",
                    description="Open incoming customer email thread",
                    target="customer_request",
                    parameters={"subject": "Inquiry: {{inputs.inquiry_type}}"},
                    output_mapping={"email_opened": "data.status"},
                ),
                WorkflowStep(
                    id="step_download_attachment",
                    name="Download Attachment",
                    type="download_attachment",
                    application="demo_email",
                    description="Download inquiry attachment if available",
                    target="invoice_pdf",
                    parameters={},
                    retry_policy=RetryPolicy(max_retries=1, backoff_seconds=0.5),
                    continue_on_failure=True,
                ),
                WorkflowStep(
                    id="step_search_crm",
                    name="Search CRM for Customer",
                    type="search_customer",
                    application="demo_crm",
                    description="Locate customer account in CRM",
                    target="{{inputs.customer_name}}",
                    parameters={"query": "{{inputs.customer_name}}"},
                    output_mapping={"crm_found": "data.success"},
                ),
                WorkflowStep(
                    id="step_update_crm",
                    name="Update CRM Record",
                    type="update_customer",
                    application="demo_crm",
                    description="Update customer interaction timestamp and notes",
                    target="{{inputs.customer_name}}",
                    parameters={"status": "In Progress", "customer": "{{inputs.customer_name}}"},
                ),
                WorkflowStep(
                    id="step_notify_chat",
                    name="Send Chat Notification",
                    type="send_message",
                    application="demo_chat",
                    description="Notify team and customer that inquiry is in progress",
                    target="support_channel",
                    parameters={"recipient": "{{inputs.customer_name}}", "message": "Inquiry received and CRM updated."},
                ),
            ],
            requires_approval=True,
            created_at=now_iso,
            updated_at=now_iso,
        )
        self._workflows[template1.id] = template1

        template2 = WorkflowDefinition(
            id="wf_gmail_triage_pipeline",
            name="Gmail Inbox Triage & Customer Lookup",
            description="Reads recent unread emails from Gmail, extracts sender inquiries, and queries CRM.",
            version="1.0.0",
            trigger=WorkflowTriggerConfig(
                type="manual",
                application="gmail",
                description="Manual trigger to inspect unread Gmail inquiries"
            ),
            inputs=[
                WorkflowInputDefinition(
                    name="query",
                    type="string",
                    default="is:unread",
                    required=False,
                    description="Gmail filter query"
                ),
                WorkflowInputDefinition(
                    name="max_messages",
                    type="integer",
                    default=5,
                    required=False,
                    description="Maximum number of messages to fetch (1-20)"
                ),
            ],
            steps=[
                WorkflowStep(
                    id="step_list_gmail",
                    name="List Recent Gmail Messages",
                    type="list_recent_messages",
                    application="gmail",
                    description="Fetch recent email headers and snippets from Gmail",
                    parameters={"max_results": "{{inputs.max_messages}}", "query": "{{inputs.query}}"},
                    output_mapping={"retrieved_count": "data.count"},
                    retry_policy=RetryPolicy(max_retries=1, backoff_seconds=1.0),
                ),
                WorkflowStep(
                    id="step_search_crm",
                    name="Search CRM for Customer",
                    type="search_customer",
                    application="demo_crm",
                    description="Query customer profile in CRM",
                    parameters={"customer_name": "Rahul Sharma"},
                    continue_on_failure=True,
                ),
            ],
            requires_approval=True,
            created_at=now_iso,
            updated_at=now_iso,
        )
        self._workflows[template2.id] = template2

    def register_workflow(self, workflow: WorkflowDefinition) -> WorkflowDefinition:
        """Saves or updates a declarative workflow definition."""
        if not workflow.id or not str(workflow.id).strip():
            import uuid
            workflow.id = f"wf_{uuid.uuid4().hex[:12]}"
        workflow.updated_at = datetime.now(timezone.utc).isoformat()
        if not workflow.created_at:
            workflow.created_at = workflow.updated_at
        self._workflows[workflow.id] = workflow
        return workflow

    def get_workflow(self, workflow_id: str) -> Optional[WorkflowDefinition]:
        """Retrieves a registered workflow definition by ID."""
        return self._workflows.get(workflow_id)

    def list_workflows(self) -> List[WorkflowDefinition]:
        """Returns all registered declarative workflow definitions."""
        return list(self._workflows.values())

    async def run_declarative_workflow(
        self,
        workflow: WorkflowDefinition,
        approved: bool = False,
        executor: Optional[ActionExecutor] = None,
        executor_type: Optional[str] = None,
        inputs: Optional[Dict[str, Any]] = None,
        parameters: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
        expected_definition_hash: Optional[str] = None,
    ) -> AutomationExecution:
        """
        Executes a Phase 6 declarative WorkflowDefinition through the automation engine.
        Supports idempotency deduplication, progress updates, and durable persistence.
        """
        if idempotency_key:
            existing = self.find_by_idempotency_key(idempotency_key)
            if existing:
                logger.info(
                    f"[AutomationService] Idempotent request match: key '{idempotency_key}' mapped to "
                    f"existing execution '{existing.execution_id}' ({existing.status}). Skipping duplicate run."
                )
                return existing

        active_executor = executor
        if active_executor is None and executor_type:
            if executor_type.lower() == "playwright":
                from automation.playwright_executor import PlaywrightExecutor
                active_executor = PlaywrightExecutor()
            elif executor_type.lower() == "noop":
                from automation.executor import NoOpExecutor
                fail_actions = (parameters or {}).get("fail_actions") or (context or {}).get("fail_actions")
                active_executor = NoOpExecutor(fail_actions=fail_actions)
            elif executor_type.lower() == "integration":
                from integrations.executor import IntegrationExecutor
                active_executor = IntegrationExecutor()

        execution = await self._engine.execute_declarative_workflow(
            workflow=workflow,
            approved=approved,
            executor=active_executor,
            inputs=inputs,
            parameters=parameters,
            context=context,
            progress_callback=self._on_progress_update,
            expected_definition_hash=expected_definition_hash,
            idempotency_key=idempotency_key,
        )
        execution = execution.model_copy(update={
            "executor_type": executor_type or "playwright",
            "context": context or {},
            "idempotency_key": idempotency_key,
        })
        self._executions[execution.execution_id] = execution
        await self._persist_execution(execution)
        return execution

    async def run_workflow(
        self,
        proposal: Optional[WorkflowProposal] = None,
        workflow_definition: Optional[WorkflowDefinition] = None,
        approved: bool = False,
        executor: Optional[ActionExecutor] = None,
        executor_type: Optional[str] = None,
        inputs: Optional[Dict[str, Any]] = None,
        parameters: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
        expected_definition_hash: Optional[str] = None,
    ) -> AutomationExecution:
        """
        Unified entrypoint: executes either a declarative WorkflowDefinition or a legacy WorkflowProposal.
        """
        if workflow_definition:
            return await self.run_declarative_workflow(
                workflow=workflow_definition,
                approved=approved,
                executor=executor,
                executor_type=executor_type,
                inputs=inputs,
                parameters=parameters,
                context=context,
                idempotency_key=idempotency_key,
                expected_definition_hash=expected_definition_hash,
            )

        if not proposal:
            raise ValueError("Either 'workflow_definition' or 'proposal' must be provided.")

        if idempotency_key:
            existing = self.find_by_idempotency_key(idempotency_key)
            if existing:
                logger.info(
                    f"[AutomationService] Idempotent request match: key '{idempotency_key}' mapped to "
                    f"existing execution '{existing.execution_id}' ({existing.status}). Skipping duplicate run."
                )
                return existing

        active_executor = executor
        if active_executor is None and executor_type:
            if executor_type.lower() == "playwright":
                from automation.playwright_executor import PlaywrightExecutor
                active_executor = PlaywrightExecutor()
            elif executor_type.lower() == "noop":
                from automation.executor import NoOpExecutor
                fail_actions = (parameters or {}).get("fail_actions") or (context or {}).get("fail_actions")
                active_executor = NoOpExecutor(fail_actions=fail_actions)
            elif executor_type.lower() == "integration":
                from integrations.executor import IntegrationExecutor
                active_executor = IntegrationExecutor()

        execution = await self._engine.execute_workflow(
            proposal=proposal,
            approved=approved,
            executor=active_executor,
            parameters=parameters,
            context=context,
        )
        execution = execution.model_copy(update={
            "executor_type": executor_type or "playwright",
            "context": context or {},
            "idempotency_key": idempotency_key,
        })
        self._executions[execution.execution_id] = execution
        await self._persist_execution(execution)
        return execution

    async def resume_execution(
        self,
        execution_id: str,
        executor: Optional[ActionExecutor] = None,
        executor_type: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> AutomationExecution:
        """
        Phase 4.6: Resume a PAUSED execution from the failed action.

        Validates the execution exists and is in PAUSED state with resume_available=True.
        Locates the failed action index, then delegates to engine.execute_from_index().

        :raises KeyError: If execution not found.
        :raises InvalidStateTransitionError: If execution is not PAUSED or not resumable.
        """
        execution = self._executions.get(execution_id)
        if not execution:
            raise KeyError(f"Execution '{execution_id}' not found.")

        if not is_valid_transition(execution.status, AutomationStatus.RUNNING):
            raise InvalidStateTransitionError(
                f"Cannot resume execution '{execution_id}': "
                f"current status is '{execution.status}'. Only PAUSED executions can be resumed."
            )

        if not execution.resume_available:
            raise InvalidStateTransitionError(
                f"Cannot resume execution '{execution_id}': resume_available is False."
            )

        merged_context = dict(execution.context or {})
        if context:
            merged_context.update(context)

        # Determine the index to resume from (the failed action, so it is retried)
        failed_action_type = execution.failed_action
        actions = execution.serialized_actions  # list of dicts from model_dump()
        start_index = 0
        if failed_action_type and actions:
            for idx, act in enumerate(actions):
                if act.get("type") == failed_action_type:
                    start_index = idx
                    break

        logger.info(
            f"AutomationService: resuming execution '{execution_id}' "
            f"from index {start_index} (failed_action='{failed_action_type}')"
        )

        # Resolve executor
        active_executor = executor
        resolved_type = executor_type or execution.executor_type or "playwright"
        if active_executor is None:
            if resolved_type.lower() == "playwright":
                from automation.playwright_executor import PlaywrightExecutor
                active_executor = PlaywrightExecutor()
            elif resolved_type.lower() == "noop":
                from automation.executor import NoOpExecutor
                fail_actions = merged_context.get("fail_actions")
                active_executor = NoOpExecutor(fail_actions=fail_actions)
            elif resolved_type.lower() == "integration":
                from integrations.executor import IntegrationExecutor
                active_executor = IntegrationExecutor()

        if execution.serialized_workflow:
            updated = await self._engine.resume_declarative_workflow(
                execution=execution,
                resume_step_id=failed_action_type,
                executor=active_executor,
                parameters=parameters,
                context=merged_context,
                progress_callback=self._on_progress_update,
            )
        else:
            updated = await self._engine.execute_from_index(
                execution=execution,
                start_index=start_index,
                executor=active_executor,
                context=merged_context,
                parameters=parameters,
            )

        updated = updated.model_copy(update={
            "executor_type": resolved_type,
            "context": merged_context,
        })
        self._executions[execution_id] = updated
        await self._persist_execution(updated)
        return updated

    def cancel_execution(self, execution_id: str) -> AutomationExecution:
        """
        Phase 4.6: Cancel a PAUSED execution.

        Validates the execution exists and is in PAUSED state.
        Sets status to CANCELLED, marks resume_available=False, records cancelled_at.

        :raises KeyError: If execution not found.
        :raises InvalidStateTransitionError: If state transition is invalid.
        """
        execution = self._executions.get(execution_id)
        if not execution:
            raise KeyError(f"Execution '{execution_id}' not found.")

        if not is_valid_transition(execution.status, AutomationStatus.CANCELLED):
            raise InvalidStateTransitionError(
                f"Cannot cancel execution '{execution_id}': "
                f"invalid state transition {execution.status} → CANCELLED. "
                f"Only PAUSED, RUNNING, or PENDING executions can be cancelled."
            )

        now_iso = datetime.now(timezone.utc).isoformat()
        logger.info(f"AutomationService: cancelling execution '{execution_id}'")

        # Mutate in-place using model_copy (Pydantic v2)
        cancelled = execution.model_copy(update={
            "status": AutomationStatus.CANCELLED,
            "resume_available": False,
            "requires_human_intervention": False,
            "cancelled_at": now_iso,
            "completed_at": now_iso,
        })
        self._executions[execution_id] = cancelled
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._persist_execution(cancelled))
        except RuntimeError:
            pass
        return cancelled

    async def cancel_execution_async(self, execution_id: str) -> AutomationExecution:
        """Asynchronous version of cancel_execution that awaits durable DB persistence."""
        cancelled = self.cancel_execution(execution_id)
        await self._persist_execution(cancelled)
        return cancelled

    def get_execution(self, execution_id: str) -> Optional[AutomationExecution]:
        """
        Retrieves a recorded execution run by its ID.
        """
        return self._executions.get(execution_id)

    def list_executions(self) -> List[AutomationExecution]:
        """
        Returns all recorded execution runs.
        """
        return list(self._executions.values())


# Singleton instance
automation_service = AutomationService()

