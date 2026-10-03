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
)
from automation.engine import automation_engine, AutomationEngine, InvalidStateTransitionError
from automation.executor import ActionExecutor

logger = logging.getLogger(__name__)


class AutomationService:
    """
    Internal service layer managing workflow automation executions, definitions, and history.

    Phase 6 adds:
    - Declarative workflow registration and execution
    - Template registry with built-in declarative workflows
    - Seamless resume for declarative and legacy workflows
    """

    def __init__(self, engine: Optional[AutomationEngine] = None):
        self._engine = engine or automation_engine
        self._executions: Dict[str, AutomationExecution] = {}
        self._workflows: Dict[str, WorkflowDefinition] = {}
        self._init_built_in_workflows()

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

    def register_workflow(self, workflow: WorkflowDefinition) -> WorkflowDefinition:
        """Saves or updates a declarative workflow definition."""
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
    ) -> AutomationExecution:
        """
        Executes a Phase 6 declarative WorkflowDefinition through the automation engine.
        """
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
        )
        execution = execution.model_copy(update={
            "executor_type": executor_type or "playwright",
            "context": context or {},
        })
        self._executions[execution.execution_id] = execution
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
            )

        if not proposal:
            raise ValueError("Either 'workflow_definition' or 'proposal' must be provided.")

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
        })
        self._executions[execution.execution_id] = execution
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

        if execution.status != AutomationStatus.PAUSED:
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

