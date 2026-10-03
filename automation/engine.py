import asyncio
import logging
import re
import uuid
import time
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Set

from ai.models import WorkflowProposal, WorkflowAction, WorkflowTrigger
from automation.models import (
    AutomationAction,
    AutomationExecution,
    AutomationStatus,
    ExecutionActionResult,
    StepCondition,
    RetryPolicy,
    WorkflowInputDefinition,
    WorkflowTriggerConfig,
    WorkflowStep,
    WorkflowDefinition,
    StepExecutionResult,
    is_valid_transition,
)
from automation.executor import ActionExecutor, NoOpExecutor

logger = logging.getLogger(__name__)

# Canonical action verbs supported by the Phase 4 WorkFlowOS automation pipeline
SUPPORTED_ACTION_TYPES: Set[str] = {
    "open_email",
    "download_attachment",
    "search_customer",
    "update_customer",
    "send_message",
}

# Regex for variable interpolation: {{variable.path}}
_TEMPLATE_REGEX = re.compile(r"\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}")


def _get_nested_val(data: Any, path: str) -> Any:
    """Safely retrieves a value from a nested dict/object using dot notation."""
    if not path:
        return data
    parts = path.split(".")
    curr = data
    for part in parts:
        if curr is None:
            return None
        if isinstance(curr, dict):
            curr = curr.get(part)
        elif hasattr(curr, part):
            curr = getattr(curr, part)
        else:
            return None
    return curr


def resolve_template_value(val: Any, context: Dict[str, Any]) -> Any:
    """
    Recursively resolves {{variable}} expressions in values, strings, lists, and dicts.
    If a string consists solely of a single {{var}}, returns the actual typed value (e.g. dict or int).
    """
    if isinstance(val, str):
        match = _TEMPLATE_REGEX.fullmatch(val.strip())
        if match:
            return _get_nested_val(context, match.group(1))
        # Partial match / multiple variables in string
        def _replace_match(m):
            v = _get_nested_val(context, m.group(1))
            return "" if v is None else str(v)
        return _TEMPLATE_REGEX.sub(_replace_match, val)
    elif isinstance(val, dict):
        return {k: resolve_template_value(v, context) for k, v in val.items()}
    elif isinstance(val, list):
        return [resolve_template_value(item, context) for item in val]
    return val


def evaluate_step_condition(condition: StepCondition, context: Dict[str, Any]) -> bool:
    """
    Evaluates a StepCondition against runtime context.
    Operators: ==, !=, >, <, >=, <=, contains, in, is_empty, is_not_empty, exists
    """
    field_val = _get_nested_val(context, condition.field)
    target_val = resolve_template_value(condition.value, context)
    op = (condition.operator or "==").strip().lower()

    if op == "==":
        return field_val == target_val
    elif op == "!=":
        return field_val != target_val
    elif op in (">", ">=", "<", "<="):
        try:
            f_num = float(field_val)
            t_num = float(target_val)
            if op == ">": return f_num > t_num
            if op == ">=": return f_num >= t_num
            if op == "<": return f_num < t_num
            if op == "<=": return f_num <= t_num
        except (ValueError, TypeError):
            return False
    elif op == "contains":
        if field_val is None:
            return False
        return str(target_val) in str(field_val)
    elif op == "in":
        if target_val is None:
            return False
        if isinstance(target_val, (list, tuple, set)):
            return field_val in target_val
        return str(field_val) in str(target_val)
    elif op == "is_empty":
        return field_val is None or field_val == "" or (isinstance(field_val, (list, dict, set)) and len(field_val) == 0)
    elif op == "is_not_empty":
        return not (field_val is None or field_val == "" or (isinstance(field_val, (list, dict, set)) and len(field_val) == 0))
    elif op == "exists":
        return field_val is not None
    else:
        logger.warning(f"Unknown operator '{op}' in StepCondition; defaulting to equality.")
        return field_val == target_val


def proposal_to_workflow_definition(
    proposal: WorkflowProposal,
    parameters: Optional[Dict[str, Any]] = None
) -> WorkflowDefinition:
    """
    Converts a Phase 3 WorkflowProposal to a Phase 6 declarative WorkflowDefinition.
    Ensures seamless backward compatibility.
    """
    wf_id = f"wf_{uuid.uuid4().hex[:10]}"
    params = parameters or {}
    steps: List[WorkflowStep] = []

    for idx, act in enumerate(proposal.actions, start=1):
        step_id = f"act_{idx:02d}_{act.type}"
        steps.append(
            WorkflowStep(
                id=step_id,
                name=act.description or act.type.replace("_", " ").title(),
                type=act.type,
                application=act.application,
                description=act.description,
                target=act.target,
                parameters=params.get(step_id, {}),
            )
        )

    inputs = [
        WorkflowInputDefinition(
            name=v,
            type="string",
            description=f"Input parameter {v}"
        ) for v in (proposal.variables or [])
    ]

    now_iso = datetime.now(timezone.utc).isoformat()
    return WorkflowDefinition(
        id=wf_id,
        name=proposal.name,
        description=proposal.intent,
        version="1.0.0",
        trigger=WorkflowTriggerConfig(
            type=proposal.trigger.type if proposal.trigger else "manual",
            application=proposal.trigger.application if proposal.trigger else None,
            description=proposal.trigger.description if proposal.trigger else None,
        ),
        inputs=inputs,
        variables={},
        steps=steps,
        requires_approval=proposal.requires_approval,
        created_at=now_iso,
        updated_at=now_iso,
    )


class AutomationEngineError(Exception):
    """Base exception for automation engine errors."""
    pass


class UnsupportedActionError(AutomationEngineError):
    """Raised when a workflow contains an unsupported action verb."""
    pass


class ApprovalRequiredError(AutomationEngineError):
    """Raised when an unapproved workflow is requested to execute."""
    pass


class InvalidStateTransitionError(AutomationEngineError):
    """Raised when a requested state transition is not allowed by the state machine."""
    pass


class AutomationEngine:
    """
    Core engine responsible for translating Phase 3 WorkflowProposal definitions
    into validated AutomationAction sequences, applying human approval safety gates,
    and coordinating sequential action execution through the ActionExecutor interface.

    Phase 4.6 adds:
    - PAUSED execution status when an action fails (enabling human-in-the-loop)
    - execute_from_index(): resume from a specific action without re-running completed actions
    - State machine transition enforcement via is_valid_transition()
    """

    def __init__(self, default_executor: Optional[ActionExecutor] = None):
        self._default_executor = default_executor or NoOpExecutor()

    def validate_and_convert_actions(
        self,
        workflow_actions: List[WorkflowAction],
        parameters: Optional[Dict[str, Any]] = None
    ) -> List[AutomationAction]:
        """
        Validates action verbs against supported types and converts WorkflowAction
        objects into executable AutomationAction objects preserving strict order.

        :param workflow_actions: Ordered list of actions from WorkflowProposal.
        :param parameters: Optional execution parameters.
        :return: Ordered list of AutomationAction instances.
        :raises UnsupportedActionError: If any action type is not supported.
        """
        if not workflow_actions:
            raise AutomationEngineError("Cannot convert an empty action list.")

        params = parameters or {}
        automation_actions: List[AutomationAction] = []

        for idx, act in enumerate(workflow_actions, start=1):
            action_type = act.type.strip().lower()

            from integrations.registry import integration_registry
            app_id = act.application.split(":", 1)[1].strip() if act.application.startswith("integration:") else act.application.strip()
            adapter = integration_registry.get(app_id)

            if adapter:
                if action_type not in adapter.declared_action_names:
                    err_msg = (
                        f"Action step {idx} '{act.type}' is not supported by integration '{app_id}'. "
                        f"Declared actions are: {adapter.declared_action_names}"
                    )
                    logger.error(err_msg)
                    raise UnsupportedActionError(err_msg)
            elif action_type not in SUPPORTED_ACTION_TYPES:
                supported_list = sorted(list(SUPPORTED_ACTION_TYPES))
                err_msg = (
                    f"Action step {idx} '{act.type}' is not supported for automation. "
                    f"Supported actions are: {supported_list}"
                )
                logger.error(err_msg)
                raise UnsupportedActionError(err_msg)

            action_id = f"act_{idx:02d}_{action_type}"
            automation_actions.append(
                AutomationAction(
                    id=action_id,
                    type=action_type,
                    application=act.application,
                    description=act.description,
                    target=act.target,
                    parameters=params.get(action_id, {}),
                )
            )

        return automation_actions

    def _build_actions_detail(
        self,
        all_actions: List[AutomationAction],
        completed: List[str],
        action_results: List[ExecutionActionResult],
        failed_action_id: Optional[str] = None,
        is_pending: bool = False,
        paused: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Build the actions_detail list from the current execution state.

        Phase 4.6 change:
        - When paused=True: actions after the failed action stay as 'pending'
          (they are NOT marked 'skipped' — they will be retried on resume).
        - When not paused (i.e. terminal FAILED): actions after failure are 'skipped'.
        """
        details = []
        for act in all_actions:
            if is_pending:
                act_status = "pending"
                msg = "Pending human approval"
            elif act.type in completed:
                act_status = "completed"
                res = next((r for r in action_results if r.action_id == act.id), None)
                msg = res.message if res else "Completed successfully"
            elif act.id == failed_action_id or (failed_action_id and act.type == failed_action_id):
                act_status = "failed"
                res = next((r for r in action_results if r.action_id == act.id), None)
                msg = res.message if res else "Action execution failed"
            else:
                # Post-failure action
                if paused:
                    act_status = "pending"   # Will be retried after human intervention
                    msg = "Pending — awaiting human intervention to resume"
                else:
                    act_status = "skipped"
                    msg = "Not executed (halted after prior action failure)"

            details.append({
                "action": act.type,
                "action_id": act.id,
                "description": act.description,
                "application": act.application,
                "target": act.target,
                "status": act_status,
                "message": msg,
            })
        return details

    async def execute_workflow(
        self,
        proposal: WorkflowProposal,
        approved: bool = False,
        executor: Optional[ActionExecutor] = None,
        parameters: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> AutomationExecution:
        """
        Executes a workflow proposal after validating approval and action types.

        Phase 4.6 behaviour change:
        - When an action fails, execution status is set to PAUSED (not FAILED).
        - requires_human_intervention=True and resume_available=True are set.
        - Actions after the failed action remain PENDING (not SKIPPED).
        - The serialized action list is stored on the execution for resume support.

        APPROVAL SAFETY GATE:
        - If approved is False, execution is refused immediately.
        - Status is set to AutomationStatus.PENDING with 0 completed actions.
        """
        start_time = time.perf_counter()
        started_at = datetime.now(timezone.utc).isoformat()
        execution_id = f"exec_{uuid.uuid4().hex[:12]}"
        total_actions = len(proposal.actions)
        applications = list(dict.fromkeys(
            proposal.applications or [act.application for act in proposal.actions if act.application]
        ))

        logger.info(
            f"Initiating automation engine for workflow: '{proposal.name}' "
            f"(execution_id={execution_id}, approved={approved}, actions={total_actions})"
        )

        # 1. Action Validation & Mapping
        try:
            actions = self.validate_and_convert_actions(
                proposal.actions,
                parameters=parameters
            )
        except UnsupportedActionError as uae:
            logger.error(f"Workflow '{proposal.name}' action validation failed: {uae}")
            now_iso = datetime.now(timezone.utc).isoformat()
            exec_obj = AutomationExecution(
                execution_id=execution_id,
                workflow_name=proposal.name,
                status=AutomationStatus.FAILED,
                current_action=None,
                completed_actions=[],
                total_actions=total_actions,
                error=str(uae),
                requires_human_intervention=False,
                results=[],
                started_at=started_at,
                completed_at=now_iso,
                execution_time_seconds=round(time.perf_counter() - start_time, 3),
                applications=applications,
                actions_detail=[],
                all_actions=[],
            )
            return exec_obj

        # 2. Approval Safety Gate
        if not approved:
            logger.info(
                f"Workflow '{proposal.name}' is unapproved. Refusing execution (status=pending)."
            )
            actions_detail = self._build_actions_detail(actions, [], [], is_pending=True)
            exec_obj = AutomationExecution(
                execution_id=execution_id,
                workflow_name=proposal.name,
                status=AutomationStatus.PENDING,
                current_action=None,
                completed_actions=[],
                total_actions=len(actions),
                error=None,
                requires_human_intervention=False,
                results=[],
                started_at=started_at,
                completed_at=started_at,
                execution_time_seconds=0.0,
                applications=applications,
                actions_detail=actions_detail,
                all_actions=actions_detail,
            )
            return exec_obj

        # 3. Approved Execution — delegate to internal runner
        return await self._run_actions(
            actions=actions,
            execution_id=execution_id,
            workflow_name=proposal.name,
            start_index=0,
            prior_completed=[],
            prior_results=[],
            start_time=start_time,
            started_at=started_at,
            applications=applications,
            executor=executor,
            context=context,
            resume_count=0,
            resumed_at=None,
        )

    async def execute_from_index(
        self,
        execution: AutomationExecution,
        start_index: int,
        executor: Optional[ActionExecutor] = None,
        context: Optional[Dict[str, Any]] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> AutomationExecution:
        """
        Phase 4.6: Resume execution from a specific action index.

        Reconstructs AutomationAction objects from the serialized list stored on the
        execution, then runs only the actions at and after start_index.
        Already-completed actions are NOT re-executed.

        :param execution: The existing PAUSED AutomationExecution.
        :param start_index: Zero-based index of the first action to (re-)execute.
        :param executor: Optional executor override.
        :param context: Optional runtime context.
        :param parameters: Optional updated action parameters.
        :return: Updated AutomationExecution with final status.
        """
        if not is_valid_transition(execution.status, AutomationStatus.RUNNING):
            raise InvalidStateTransitionError(
                f"Cannot resume execution '{execution.execution_id}': "
                f"invalid state transition {execution.status} → RUNNING. "
                f"Only PAUSED executions can be resumed."
            )

        # Reconstruct actions from serialized list
        actions = [AutomationAction(**a) for a in execution.serialized_actions]
        if parameters:
            for act in actions:
                if act.id in parameters:
                    act.parameters.update(parameters[act.id])
                elif act.type in parameters:
                    act.parameters.update(parameters[act.type])

        prior_completed = list(execution.completed_actions)
        # Keep only results of actions completed prior to start_index (deduplicate retried action)
        prior_results = [r for r in execution.results if r.success and r.action_type in prior_completed]
        now_iso = datetime.now(timezone.utc).isoformat()

        logger.info(
            f"Resuming execution '{execution.execution_id}' from action index {start_index} "
            f"(already completed: {prior_completed})"
        )

        return await self._run_actions(
            actions=actions,
            execution_id=execution.execution_id,
            workflow_name=execution.workflow_name,
            start_index=start_index,
            prior_completed=prior_completed,
            prior_results=prior_results,
            start_time=time.perf_counter(),
            started_at=execution.started_at or now_iso,
            applications=execution.applications,
            executor=executor,
            context=context,
            resume_count=execution.resume_count + 1,
            resumed_at=now_iso,
            accumulated_time=execution.execution_time_seconds or 0.0,
        )

    async def _run_actions(
        self,
        actions: List[AutomationAction],
        execution_id: str,
        workflow_name: str,
        start_index: int,
        prior_completed: List[str],
        prior_results: List[ExecutionActionResult],
        start_time: float,
        started_at: str,
        applications: List[str],
        executor: Optional[ActionExecutor],
        context: Optional[Dict[str, Any]],
        resume_count: int,
        resumed_at: Optional[str],
        accumulated_time: float = 0.0,
    ) -> AutomationExecution:
        """
        Internal sequential execution runner.
        Runs actions[start_index:] with the given executor.
        Carries forward completed actions from prior_completed.
        """
        active_executor = executor or self._default_executor
        completed_actions: List[str] = list(prior_completed)
        results: List[ExecutionActionResult] = list(prior_results)
        execution_logs: List[str] = [
            f"Approval confirmed. Executing {len(actions) - start_index} actions sequentially via {active_executor.__class__.__name__}."
        ]

        logger.info(
            f"Approval confirmed. Executing {len(actions) - start_index} actions "
            f"(index {start_index}–{len(actions) - 1}) sequentially "
            f"via {active_executor.__class__.__name__}..."
        )

        # Serialise full action list for potential future resumes
        serialized_actions = [a.model_dump() for a in actions]
        step_results: List[StepExecutionResult] = []

        try:
            await active_executor.start()

            for idx, action in enumerate(actions):
                if idx < start_index:
                    # Skip already-completed actions
                    continue

                logger.info(f"Executing step {action.id} ({action.type})...")
                execution_logs.append(f"Executing action '{action.id}' ({action.type}) on '{action.application}'")
                step_start_iso = datetime.now(timezone.utc).isoformat()
                try:
                    result = await active_executor.execute(action, context=context)
                    results.append(result)
                except Exception as e:
                    logger.error(f"Unexpected exception executing {action.id}: {e}", exc_info=True)
                    result = ExecutionActionResult(
                        action_id=action.id,
                        action_type=action.type,
                        success=False,
                        message=f"Executor exception: {str(e)}"
                    )
                    results.append(result)

                now_step_iso = datetime.now(timezone.utc).isoformat()
                step_results.append(
                    StepExecutionResult(
                        step_id=action.id,
                        action_type=action.type,
                        application=action.application,
                        status="completed" if result.success else "failed",
                        attempts=1,
                        started_at=step_start_iso,
                        completed_at=now_step_iso,
                        inputs=action.parameters,
                        outputs=result.data or {},
                        logs=[f"Action {action.id} ({action.type}): {result.message}"],
                        error=None if result.success else result.message,
                    )
                )

                if not result.success:
                    # ── Phase 4.6: PAUSED instead of FAILED ─────────────
                    logger.warning(
                        f"Action {action.id} failed: {result.message}. "
                        f"Execution PAUSED — human intervention required."
                    )
                    execution_logs.append(f"Action '{action.id}' failed: {result.message}. Execution PAUSED.")
                    elapsed = round(accumulated_time + (time.perf_counter() - start_time), 3)
                    now_iso = datetime.now(timezone.utc).isoformat()
                    actions_detail = self._build_actions_detail(
                        actions,
                        completed_actions,
                        results,
                        failed_action_id=action.id,
                        paused=True,    # post-failure actions stay PENDING, not SKIPPED
                    )
                    return AutomationExecution(
                        execution_id=execution_id,
                        workflow_name=workflow_name,
                        status=AutomationStatus.PAUSED,
                        current_action=action.type,
                        completed_actions=completed_actions,
                        total_actions=len(actions),
                        error=result.message,
                        requires_human_intervention=True,
                        # Phase 4.6
                        failed_action=action.type,
                        failure_reason=result.message,
                        resume_available=True,
                        resume_count=resume_count,
                        paused_at=now_iso,
                        resumed_at=resumed_at,
                        serialized_actions=serialized_actions,
                        context=context or {},
                        inputs={},
                        variables={},
                        step_results=step_results,
                        execution_logs=execution_logs,
                        results=results,
                        started_at=started_at,
                        completed_at=None,
                        execution_time_seconds=elapsed,
                        applications=applications,
                        actions_detail=actions_detail,
                        all_actions=actions_detail,
                    )

                # Record completed action
                completed_actions.append(action.type)

            # ── All actions completed successfully ────────────────────────
            logger.info(
                f"Workflow '{workflow_name}' completed successfully "
                f"({len(completed_actions)}/{len(actions)} actions)."
            )
            execution_logs.append(f"Workflow '{workflow_name}' completed successfully ({len(completed_actions)} actions).")
            elapsed = round(accumulated_time + (time.perf_counter() - start_time), 3)
            now_iso = datetime.now(timezone.utc).isoformat()
            actions_detail = self._build_actions_detail(actions, completed_actions, results)
            return AutomationExecution(
                execution_id=execution_id,
                workflow_name=workflow_name,
                status=AutomationStatus.COMPLETED,
                current_action=None,
                completed_actions=completed_actions,
                total_actions=len(actions),
                error=None,
                requires_human_intervention=False,
                # Phase 4.6
                failed_action=None,
                failure_reason=None,
                resume_available=False,
                resume_count=resume_count,
                resumed_at=resumed_at,
                serialized_actions=serialized_actions,
                context=context or {},
                inputs={},
                variables={},
                step_results=step_results,
                execution_logs=execution_logs,
                results=results,
                started_at=started_at,
                completed_at=now_iso,
                execution_time_seconds=elapsed,
                applications=applications,
                actions_detail=actions_detail,
                all_actions=actions_detail,
            )
        finally:
            await active_executor.cleanup()

    # -----------------------------------------------------------------------
    # Phase 6: Declarative Workflow Execution Engine
    # -----------------------------------------------------------------------

    async def execute_declarative_workflow(
        self,
        workflow: WorkflowDefinition,
        approved: bool = False,
        executor: Optional[ActionExecutor] = None,
        inputs: Optional[Dict[str, Any]] = None,
        parameters: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> AutomationExecution:
        """
        Executes a declarative WorkflowDefinition supporting configurable triggers,
        ordered steps, input validation, variable interpolation, conditional branching,
        retry policies, and output mapping.
        """
        start_time = time.perf_counter()
        started_at = datetime.now(timezone.utc).isoformat()
        execution_id = f"exec_{uuid.uuid4().hex[:12]}"
        applications = list(dict.fromkeys(
            s.application for s in workflow.steps if s.application and s.application != "workflow_system"
        ))

        # 1. Inputs validation & defaults
        merged_inputs = {}
        for inp in workflow.inputs:
            if inp.default is not None:
                merged_inputs[inp.name] = inp.default
        if inputs:
            merged_inputs.update(inputs)
        if parameters:
            merged_inputs.update(parameters)

        missing_required = [
            inp.name for inp in workflow.inputs
            if inp.required and inp.name not in merged_inputs
        ]
        if missing_required:
            err_msg = f"Missing required workflow inputs: {missing_required}"
            logger.error(err_msg)
            now_iso = datetime.now(timezone.utc).isoformat()
            return AutomationExecution(
                execution_id=execution_id,
                workflow_id=workflow.id,
                workflow_name=workflow.name,
                status=AutomationStatus.FAILED,
                error=err_msg,
                total_actions=len(workflow.steps),
                inputs=merged_inputs,
                variables=dict(workflow.variables),
                execution_logs=[err_msg],
                started_at=started_at,
                completed_at=now_iso,
                execution_time_seconds=0.0,
                applications=applications,
            )

        # 2. Action Type & Parameter Schema Validation
        from integrations.registry import integration_registry
        for idx, step in enumerate(workflow.steps, start=1):
            app_id = step.application.split(":", 1)[1].strip() if step.application.startswith("integration:") else step.application.strip()
            adapter = integration_registry.get(app_id)
            if adapter:
                if step.type not in adapter.declared_action_names:
                    err_msg = (
                        f"Workflow step {idx} '{step.type}' is not supported by integration '{app_id}'. "
                        f"Declared actions are: {adapter.declared_action_names}"
                    )
                    logger.error(err_msg)
                    now_iso = datetime.now(timezone.utc).isoformat()
                    return AutomationExecution(
                        execution_id=execution_id,
                        workflow_id=workflow.id,
                        workflow_name=workflow.name,
                        status=AutomationStatus.FAILED,
                        error=err_msg,
                        total_actions=len(workflow.steps),
                        inputs=merged_inputs,
                        variables=dict(workflow.variables),
                        execution_logs=[err_msg],
                        started_at=started_at,
                        completed_at=now_iso,
                        execution_time_seconds=0.0,
                        applications=applications,
                    )
                # Static input validation if not template-guarded
                has_templates = any(
                    isinstance(v, str) and "{{" in v for v in (step.parameters or {}).values()
                )
                if not has_templates:
                    is_valid, val_err = adapter.validate_action_inputs(step.type, step.parameters or {})
                    if not is_valid:
                        err_msg = f"Workflow step {idx} '{step.type}' parameter validation failed: {val_err}"
                        logger.error(err_msg)
                        now_iso = datetime.now(timezone.utc).isoformat()
                        return AutomationExecution(
                            execution_id=execution_id,
                            workflow_id=workflow.id,
                            workflow_name=workflow.name,
                            status=AutomationStatus.FAILED,
                            error=err_msg,
                            total_actions=len(workflow.steps),
                            inputs=merged_inputs,
                            variables=dict(workflow.variables),
                            execution_logs=[err_msg],
                            started_at=started_at,
                            completed_at=now_iso,
                            execution_time_seconds=0.0,
                            applications=applications,
                        )
            elif step.type not in SUPPORTED_ACTION_TYPES and step.type not in ("condition", "wait", "transform", "log"):
                err_msg = (
                    f"Workflow step {idx} '{step.type}' is not supported for automation. "
                    f"Supported actions are: {sorted(list(SUPPORTED_ACTION_TYPES))}"
                )
                logger.error(err_msg)
                now_iso = datetime.now(timezone.utc).isoformat()
                return AutomationExecution(
                    execution_id=execution_id,
                    workflow_id=workflow.id,
                    workflow_name=workflow.name,
                    status=AutomationStatus.FAILED,
                    error=err_msg,
                    total_actions=len(workflow.steps),
                    inputs=merged_inputs,
                    variables=dict(workflow.variables),
                    execution_logs=[err_msg],
                    started_at=started_at,
                    completed_at=now_iso,
                    execution_time_seconds=0.0,
                    applications=applications,
                )

        # 3. Approval Gate
        if workflow.requires_approval and not approved:
            logger.info(f"Declarative workflow '{workflow.name}' is unapproved. Refusing execution.")
            actions_detail = [
                {
                    "action": s.type,
                    "action_id": s.id,
                    "description": s.description or s.name or s.type,
                    "application": s.application,
                    "target": s.target or "",
                    "status": "pending",
                    "message": "Pending human approval",
                }
                for s in workflow.steps
            ]
            return AutomationExecution(
                execution_id=execution_id,
                workflow_id=workflow.id,
                workflow_name=workflow.name,
                status=AutomationStatus.PENDING,
                completed_actions=[],
                total_actions=len(workflow.steps),
                inputs=merged_inputs,
                variables=dict(workflow.variables),
                serialized_workflow=workflow.model_dump(),
                started_at=started_at,
                completed_at=started_at,
                execution_time_seconds=0.0,
                applications=applications,
                actions_detail=actions_detail,
                all_actions=actions_detail,
                execution_logs=["Workflow awaiting human approval before execution"],
            )

        # 4. Execute steps
        return await self._run_declarative_steps(
            workflow=workflow,
            execution_id=execution_id,
            start_step_idx=0,
            merged_inputs=merged_inputs,
            variables=dict(workflow.variables),
            prior_step_results=[],
            prior_completed=[],
            prior_results=[],
            prior_logs=[],
            start_time=start_time,
            started_at=started_at,
            applications=applications,
            executor=executor,
            context=context,
            resume_count=0,
            resumed_at=None,
        )

    async def _run_declarative_steps(
        self,
        workflow: WorkflowDefinition,
        execution_id: str,
        start_step_idx: int,
        merged_inputs: Dict[str, Any],
        variables: Dict[str, Any],
        prior_step_results: List[StepExecutionResult],
        prior_completed: List[str],
        prior_results: List[ExecutionActionResult],
        prior_logs: List[str],
        start_time: float,
        started_at: str,
        applications: List[str],
        executor: Optional[ActionExecutor],
        context: Optional[Dict[str, Any]],
        resume_count: int,
        resumed_at: Optional[str],
        accumulated_time: float = 0.0,
    ) -> AutomationExecution:
        active_executor = executor or self._default_executor
        runtime_context = dict(context or {})
        runtime_context["inputs"] = dict(merged_inputs)
        runtime_context["variables"] = dict(variables)
        runtime_context["steps"] = {}
        for sr in prior_step_results:
            runtime_context["steps"][sr.step_id] = {
                "status": sr.status,
                "output": sr.outputs,
                "data": sr.outputs,
                "error": sr.error,
            }

        step_results: List[StepExecutionResult] = list(prior_step_results)
        completed_actions: List[str] = list(prior_completed)
        results: List[ExecutionActionResult] = list(prior_results)
        execution_logs: List[str] = list(prior_logs)

        step_map = {s.id: s for s in workflow.steps}
        step_ids = [s.id for s in workflow.steps]
        curr_idx = start_step_idx

        serialized_actions = [
            {
                "id": s.id,
                "type": s.type,
                "application": s.application,
                "description": s.description or s.name or s.type,
                "target": s.target or "",
                "parameters": s.parameters or {},
            }
            for s in workflow.steps
        ]

        try:
            await active_executor.start()

            while curr_idx < len(step_ids):
                step = step_map[step_ids[curr_idx]]
                step_start_iso = datetime.now(timezone.utc).isoformat()
                step_logs = []
                execution_logs.append(f"Evaluating step '{step.id}' ({step.type}) on '{step.application}'")

                # Condition Evaluation
                if step.condition:
                    cond_met = evaluate_step_condition(step.condition, runtime_context)
                    log_cond = (
                        f"Step '{step.id}' condition evaluated {cond_met} "
                        f"({step.condition.field} {step.condition.operator} {step.condition.value})"
                    )
                    step_logs.append(log_cond)
                    execution_logs.append(log_cond)

                    if not cond_met:
                        step_results.append(
                            StepExecutionResult(
                                step_id=step.id,
                                action_type=step.type,
                                application=step.application,
                                status="skipped",
                                attempts=0,
                                started_at=step_start_iso,
                                completed_at=datetime.now(timezone.utc).isoformat(),
                                inputs={},
                                outputs={},
                                logs=step_logs + ["Condition evaluated False; step skipped"],
                            )
                        )
                        if step.on_false and step.on_false in step_map:
                            execution_logs.append(f"Branching on_false: jumping from '{step.id}' to '{step.on_false}'")
                            curr_idx = step_ids.index(step.on_false)
                        else:
                            curr_idx += 1
                        continue

                # Template Resolution for step parameters and target
                resolved_params = resolve_template_value(step.parameters or {}, runtime_context)
                resolved_target = resolve_template_value(step.target or "", runtime_context)

                # Execute action step
                action = AutomationAction(
                    id=step.id,
                    type=step.type,
                    application=step.application,
                    description=step.description or step.name or step.type,
                    target=resolved_target,
                    parameters=resolved_params,
                )

                max_retries = step.retry_policy.max_retries if step.retry_policy else 0
                backoff = step.retry_policy.backoff_seconds if step.retry_policy else 1.0
                attempts = 0
                result: Optional[ExecutionActionResult] = None

                for attempt in range(1, max_retries + 2):
                    attempts = attempt
                    try:
                        result = await active_executor.execute(action, context=runtime_context)
                    except Exception as exc:
                        result = ExecutionActionResult(
                            action_id=step.id,
                            action_type=step.type,
                            success=False,
                            message=f"Executor exception: {str(exc)}",
                        )
                    step_logs.append(f"Attempt {attempt}: success={result.success}, message='{result.message}'")
                    if result.success:
                        break
                    if attempt <= max_retries:
                        if step.retry_policy and step.retry_policy.retry_on_errors:
                            if not any(err in (result.message or "") for err in step.retry_policy.retry_on_errors):
                                step_logs.append("Error does not match retry_on_errors policy. Aborting retries.")
                                break
                        step_logs.append(f"Retrying step '{step.id}' in {backoff * attempt:.1f}s...")
                        await asyncio.sleep(backoff * attempt)

                now_iso = datetime.now(timezone.utc).isoformat()
                step_res = StepExecutionResult(
                    step_id=step.id,
                    action_type=step.type,
                    application=step.application,
                    status="completed" if result.success else "failed",
                    attempts=attempts,
                    started_at=step_start_iso,
                    completed_at=now_iso,
                    inputs=resolved_params,
                    outputs=result.data or {},
                    logs=step_logs,
                    error=None if result.success else result.message,
                )
                step_results.append(step_res)
                results.append(result)

                if result.success:
                    # Output Mapping
                    if step.output_mapping and result.data:
                        step_data_ctx = {
                            "data": result.data,
                            **(result.data if isinstance(result.data, dict) else {}),
                        }
                        for var_key, data_path in step.output_mapping.items():
                            val = _get_nested_val(step_data_ctx, data_path)
                            runtime_context["variables"][var_key] = val
                            execution_logs.append(f"Mapped output variable '{var_key}' = {val}")

                    runtime_context["steps"][step.id] = {
                        "status": "completed",
                        "output": result.data or {},
                        "data": result.data or {},
                        "message": result.message,
                    }
                    completed_actions.append(step.type)

                    # Branching on_true
                    if step.on_true and step.on_true in step_map:
                        execution_logs.append(f"Branching on_true: jumping from '{step.id}' to '{step.on_true}'")
                        curr_idx = step_ids.index(step.on_true)
                    else:
                        curr_idx += 1
                else:
                    if step.continue_on_failure:
                        execution_logs.append(f"Step '{step.id}' failed but continue_on_failure is True. Continuing.")
                        runtime_context["steps"][step.id] = {
                            "status": "failed",
                            "error": result.message,
                        }
                        curr_idx += 1
                    else:
                        # Paused for human intervention
                        execution_logs.append(f"Step '{step.id}' failed. Workflow PAUSED pending human intervention.")
                        elapsed = round(accumulated_time + (time.perf_counter() - start_time), 3)
                        actions_detail = [
                            {
                                "action": s.type,
                                "action_id": s.id,
                                "description": s.description or s.name or s.type,
                                "application": s.application,
                                "target": s.target or "",
                                "status": "completed" if s.id in [r.step_id for r in step_results if r.status == "completed"]
                                          else ("failed" if s.id == step.id else "pending"),
                                "message": next((r.logs[-1] for r in step_results if r.step_id == s.id), "Pending"),
                            }
                            for s in workflow.steps
                        ]
                        return AutomationExecution(
                            execution_id=execution_id,
                            workflow_id=workflow.id,
                            workflow_name=workflow.name,
                            status=AutomationStatus.PAUSED,
                            current_action=step.type,
                            completed_actions=completed_actions,
                            total_actions=len(workflow.steps),
                            error=result.message,
                            requires_human_intervention=True,
                            failed_action=step.type,
                            failure_reason=result.message,
                            resume_available=True,
                            resume_count=resume_count,
                            paused_at=now_iso,
                            resumed_at=resumed_at,
                            serialized_actions=serialized_actions,
                            serialized_workflow=workflow.model_dump(),
                            context=runtime_context,
                            inputs=merged_inputs,
                            variables=runtime_context.get("variables", {}),
                            step_results=step_results,
                            execution_logs=execution_logs,
                            results=results,
                            started_at=started_at,
                            completed_at=None,
                            execution_time_seconds=elapsed,
                            applications=applications,
                            actions_detail=actions_detail,
                            all_actions=actions_detail,
                        )

            # All steps completed
            elapsed = round(accumulated_time + (time.perf_counter() - start_time), 3)
            now_iso = datetime.now(timezone.utc).isoformat()
            execution_logs.append(f"Workflow '{workflow.name}' completed successfully ({len(completed_actions)} actions).")
            actions_detail = [
                {
                    "action": s.type,
                    "action_id": s.id,
                    "description": s.description or s.name or s.type,
                    "application": s.application,
                    "target": s.target or "",
                    "status": "completed" if s.id in [r.step_id for r in step_results if r.status == "completed"]
                              else ("skipped" if s.id in [r.step_id for r in step_results if r.status == "skipped"] else "failed"),
                    "message": next((r.logs[-1] for r in step_results if r.step_id == s.id), "Success"),
                }
                for s in workflow.steps
            ]
            return AutomationExecution(
                execution_id=execution_id,
                workflow_id=workflow.id,
                workflow_name=workflow.name,
                status=AutomationStatus.COMPLETED,
                current_action=None,
                completed_actions=completed_actions,
                total_actions=len(workflow.steps),
                error=None,
                requires_human_intervention=False,
                failed_action=None,
                failure_reason=None,
                resume_available=False,
                resume_count=resume_count,
                resumed_at=resumed_at,
                serialized_actions=serialized_actions,
                serialized_workflow=workflow.model_dump(),
                context=runtime_context,
                inputs=merged_inputs,
                variables=runtime_context.get("variables", {}),
                step_results=step_results,
                execution_logs=execution_logs,
                results=results,
                started_at=started_at,
                completed_at=now_iso,
                execution_time_seconds=elapsed,
                applications=applications,
                actions_detail=actions_detail,
                all_actions=actions_detail,
            )
        finally:
            await active_executor.cleanup()

    async def resume_declarative_workflow(
        self,
        execution: AutomationExecution,
        resume_step_id: Optional[str] = None,
        executor: Optional[ActionExecutor] = None,
        inputs: Optional[Dict[str, Any]] = None,
        parameters: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> AutomationExecution:
        """
        Resumes a PAUSED declarative workflow execution from the failed step.
        """
        if not is_valid_transition(execution.status, AutomationStatus.RUNNING):
            raise InvalidStateTransitionError(
                f"Cannot resume execution '{execution.execution_id}': "
                f"invalid state transition {execution.status} → RUNNING."
            )
        if not execution.serialized_workflow:
            raise AutomationEngineError(
                f"No serialized workflow definition found on execution '{execution.execution_id}'"
            )

        workflow = WorkflowDefinition(**execution.serialized_workflow)
        step_ids = [s.id for s in workflow.steps]

        target_step_id = resume_step_id or execution.failed_action
        start_step_idx = 0
        if target_step_id:
            for idx, s in enumerate(workflow.steps):
                if s.id == target_step_id or s.type == target_step_id:
                    start_step_idx = idx
                    break

        merged_inputs = dict(execution.inputs or {})
        if inputs:
            merged_inputs.update(inputs)
        if parameters:
            merged_inputs.update(parameters)

        merged_variables = dict(execution.variables or {})
        now_iso = datetime.now(timezone.utc).isoformat()

        prior_step_results = [sr for sr in execution.step_results if sr.status == "completed"]
        prior_completed = list(execution.completed_actions)
        prior_results = [r for r in execution.results if r.success]
        prior_logs = list(execution.execution_logs or [])
        prior_logs.append(
            f"Resuming execution from step '{step_ids[start_step_idx]}' (resume_count={execution.resume_count + 1})"
        )

        return await self._run_declarative_steps(
            workflow=workflow,
            execution_id=execution.execution_id,
            start_step_idx=start_step_idx,
            merged_inputs=merged_inputs,
            variables=merged_variables,
            prior_step_results=prior_step_results,
            prior_completed=prior_completed,
            prior_results=prior_results,
            prior_logs=prior_logs,
            start_time=time.perf_counter(),
            started_at=execution.started_at or now_iso,
            applications=execution.applications,
            executor=executor,
            context=context,
            resume_count=execution.resume_count + 1,
            resumed_at=now_iso,
            accumulated_time=execution.execution_time_seconds or 0.0,
        )


# Singleton instance for general use
automation_engine = AutomationEngine()



