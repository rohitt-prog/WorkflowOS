"""
WorkFlowOS Phase 11: Execution Outcome Evaluation & Failure Taxonomy

Provides deterministic evaluation of workflow executions into structured,
auditable outcome records across workflow, step, and strategy levels.

Strict Invariants:
- Deterministic heuristic evaluation (NO LLMs, embeddings, or ML models).
- Credentials, tokens, secrets, and auth headers are NEVER persisted.
- Preserves Phase 9 ExecutionLearningOutcome and interpret_execution_outcome.
"""

import logging
import re
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
from pydantic import BaseModel, Field

from automation.models import AutomationExecution, AutomationStatus
from integrations.credentials import sanitize_log_message

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Phase 11: Bounded Failure Taxonomy
# ---------------------------------------------------------------------------

class FailureCategory(str, Enum):
    """
    Standardized, bounded failure categories for deterministic root-cause tracking.
    Safe to persist and audit; contains no sensitive runtime data.
    """
    TIMEOUT = "TIMEOUT"
    AUTHENTICATION = "AUTHENTICATION"
    AUTHORIZATION = "AUTHORIZATION"
    NETWORK = "NETWORK"
    VALIDATION = "VALIDATION"
    TARGET_NOT_FOUND = "TARGET_NOT_FOUND"
    UNSUPPORTED_ACTION = "UNSUPPORTED_ACTION"
    RATE_LIMIT = "RATE_LIMIT"
    INTEGRATION_ERROR = "INTEGRATION_ERROR"
    BROWSER_ERROR = "BROWSER_ERROR"
    UNKNOWN = "UNKNOWN"


class ExecutionOutcomeStatus(str, Enum):
    """Lifecycle outcome classification for closed-loop evaluation."""
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"
    CANCELLED = "CANCELLED"
    PAUSED = "PAUSED"
    NOT_EXECUTED = "NOT_EXECUTED"



def categorize_failure(error_message: Optional[str]) -> FailureCategory:
    """
    Deterministically classifies an error message into a FailureCategory.
    Safe against None and sanitizes input.
    """
    if not error_message:
        return FailureCategory.UNKNOWN

    msg = error_message.lower().strip()

    # 1. Timeout
    if any(k in msg for k in ("timeout", "timed out", "deadline exceeded", "timedout")):
        return FailureCategory.TIMEOUT

    # 2. Authentication
    if any(k in msg for k in ("401", "unauthorized", "invalid_token", "token expired", "token revoked", "unauthenticated", "invalid credentials")):
        return FailureCategory.AUTHENTICATION

    # 3. Authorization
    if any(k in msg for k in ("403", "forbidden", "permission denied", "insufficient scope", "access denied")):
        return FailureCategory.AUTHORIZATION

    # 4. Rate Limit
    if any(k in msg for k in ("429", "rate limit", "quota exceeded", "too many requests")):
        return FailureCategory.RATE_LIMIT

    # 5. Validation / Schema
    if any(k in msg for k in ("validation error", "schema error", "422", "invalid parameter", "missing required", "invalid input")):
        return FailureCategory.VALIDATION

    # 6. Target Not Found
    if any(k in msg for k in ("not found", "target not found", "selector not found", "element not found", "404", "could not find", "waiting for selector")):
        return FailureCategory.TARGET_NOT_FOUND

    # 7. Unsupported Action
    if any(k in msg for k in ("unsupported action", "not supported", "unknown action", "handler not found")):
        return FailureCategory.UNSUPPORTED_ACTION

    # 8. Network / Connection
    if any(k in msg for k in ("connection error", "network error", "connection refused", "econnrefused", "dns error", "no route to host")):
        return FailureCategory.NETWORK

    # 9. Browser
    if any(k in msg for k in ("playwright", "browser", "page closed", "target closed", "navigation failed")):
        return FailureCategory.BROWSER_ERROR

    # 10. Integration
    if any(k in msg for k in ("integration", "adapter", "service disconnected")):
        return FailureCategory.INTEGRATION_ERROR

    return FailureCategory.UNKNOWN


# ---------------------------------------------------------------------------
# Phase 11 Models: Step and Workflow Outcomes
# ---------------------------------------------------------------------------

class StepOutcome(BaseModel):
    """
    Deterministic outcome for a single workflow action step.
    Associated with workflow + step + strategy.
    """
    step_id: str = Field(..., description="Deterministic step ID (e.g. 'step_1')")
    action: str = Field(..., description="Action verb type (e.g. 'search_customer')")
    application: str = Field(default="unknown", description="Target application")
    strategy: str = Field(..., description="Automation strategy used: API, INTEGRATION, BROWSER, MANUAL")
    status: ExecutionOutcomeStatus = Field(..., description="Outcome: SUCCESS, FAILED, PARTIAL, CANCELLED, PAUSED")
    duration_seconds: Optional[float] = Field(default=None, description="Execution duration of step in seconds")
    retries: int = Field(default=0, ge=0, description="Number of retries attempted")
    is_fallback: bool = Field(default=False, description="Whether this step executed as a fallback strategy")
    primary_strategy: Optional[str] = Field(default=None, description="Primary strategy that failed if this step executed as fallback")
    failure_category: Optional[FailureCategory] = Field(default=None, description="Categorized failure if step failed")
    error_message: Optional[str] = Field(default=None, description="Sanitized error message without credentials")


class WorkflowExecutionOutcome(BaseModel):
    """
    Complete closed-loop outcome evaluation for a workflow execution run.
    """
    workflow_id: str = Field(..., description="Canonical workflow ID")
    execution_id: str = Field(..., description="Execution identifier")
    status: ExecutionOutcomeStatus = Field(..., description="Overall status: SUCCESS, FAILED, PARTIAL, CANCELLED, PAUSED")
    started_at: str = Field(..., description="ISO 8601 UTC execution start timestamp")
    completed_at: Optional[str] = Field(default=None, description="ISO 8601 UTC completion timestamp")
    duration_seconds: Optional[float] = Field(default=None, description="Total execution duration in seconds")
    total_steps: int = Field(default=0, ge=0, description="Total configured workflow steps")
    completed_steps: int = Field(default=0, ge=0, description="Count of successfully executed steps")
    failed_steps_count: int = Field(default=0, ge=0, description="Count of failed steps")
    unexecuted_steps_count: int = Field(default=0, ge=0, description="Count of steps not reached/executed")
    failed_step: Optional[str] = Field(default=None, description="Action verb or step_id that failed, if any")
    failure_category: Optional[FailureCategory] = Field(default=None, description="Root failure category")
    fallback_used: bool = Field(default=False, description="Whether any step used a fallback strategy")
    step_outcomes: List[StepOutcome] = Field(default_factory=list, description="Per-step outcome evaluations")
    error_message: Optional[str] = Field(default=None, description="Sanitized overall failure explanation")


# ---------------------------------------------------------------------------
# Phase 11: Deterministic Outcome Evaluator
# ---------------------------------------------------------------------------

def _infer_strategy_for_step(
    action_type: str,
    application: str,
    executor_type: Optional[str],
    context: Dict[str, Any],
    step_id: Optional[str] = None,
) -> str:
    """Deterministically resolves the automation strategy used for a step."""
    ctx_strategies = context.get("step_strategies") or {}
    if step_id and step_id in ctx_strategies:
        return str(ctx_strategies[step_id]).upper()
    if action_type in ctx_strategies:
        return str(ctx_strategies[action_type]).upper()

    plan = context.get("automation_plan") or {}
    if isinstance(plan, dict):
        steps = plan.get("steps") or []
        for s in steps:
            s_action = s.get("action")
            s_id = s.get("step_id")
            if (step_id and s_id == step_id) or (s_action == action_type):
                strat = s.get("selected_strategy")
                if strat:
                    return str(strat).upper()

    # Context strategy override
    if context.get("strategy"):
        return str(context["strategy"]).upper()

    # Executor type mapping
    exec_type = (executor_type or "").lower()
    if exec_type == "playwright":
        return "BROWSER"
    if exec_type == "integration":
        return "INTEGRATION"

    # Application / action mapping
    app_lower = (application or "").lower()
    if "integration:" in app_lower or "gmail" in app_lower or "mock" in app_lower:
        if action_type in ("simulate_ping", "mock_echo", "list_recent_messages"):
            return "API"
        return "INTEGRATION"

    if action_type in ("open_email", "download_attachment", "search_customer", "update_customer", "send_message"):
        return "BROWSER"

    return "MANUAL"


def evaluate_execution_outcome(
    execution: AutomationExecution,
    target_workflow_id: Optional[str] = None,
    step_strategies: Optional[Dict[str, str]] = None,
) -> Optional[WorkflowExecutionOutcome]:
    """
    Evaluates an AutomationExecution into a structured WorkflowExecutionOutcome.
    Returns None if execution is PENDING or RUNNING.
    """
    if execution.status in (AutomationStatus.PENDING, AutomationStatus.RUNNING):
        return None

    # Resolve workflow ID
    resolved_id = target_workflow_id or execution.workflow_id
    if not resolved_id:
        if execution.workflow_name:
            slug = re.sub(r"[^a-zA-Z0-9_]+", "_", execution.workflow_name.strip().lower())
            resolved_id = f"wf_{slug}"
        else:
            resolved_id = "wf_unknown"

    exec_context = dict(execution.context or {})
    if step_strategies:
        existing_strat = exec_context.setdefault("step_strategies", {})
        existing_strat.update(step_strategies)

    # 1. Map Overall Status
    exec_status = execution.status
    if exec_status == AutomationStatus.CANCELLED:
        overall_status = ExecutionOutcomeStatus.CANCELLED
    elif exec_status == AutomationStatus.PAUSED:
        overall_status = ExecutionOutcomeStatus.PAUSED
    elif exec_status == AutomationStatus.COMPLETED:
        overall_status = ExecutionOutcomeStatus.SUCCESS
    elif exec_status == AutomationStatus.FAILED:
        # Check if partial (some actions completed prior to failure)
        if execution.completed_actions and len(execution.completed_actions) > 0 and len(execution.completed_actions) < execution.total_actions:
            overall_status = ExecutionOutcomeStatus.PARTIAL
        else:
            overall_status = ExecutionOutcomeStatus.FAILED
    else:
        overall_status = ExecutionOutcomeStatus.FAILED

    # 2. Evaluate Steps
    step_outcomes: List[StepOutcome] = []
    actions_detail = list(execution.actions_detail or [])
    results_list = list(execution.results or [])
    step_results = list(execution.step_results or [])

    total_steps = execution.total_actions or len(actions_detail) or len(results_list)
    completed_count = len(execution.completed_actions or [])
    failed_steps_count = 0
    fallback_used = bool(exec_context.get("fallback_used", False))

    def _resolve_step_fallback(
        s_id: str,
        a_type: str,
        idx: int,
        strat: str,
        step_obj: Any,
    ) -> Tuple[bool, Optional[str]]:
        is_fb = False
        if getattr(step_obj, "is_fallback", False) or getattr(step_obj, "fallback_used", False):
            is_fb = True
        elif s_id in exec_context.get("fallback_step_ids", []):
            is_fb = True
        elif idx in exec_context.get("fallback_step_indices", []):
            is_fb = True
        elif a_type in exec_context.get("fallback_actions", []):
            is_fb = True
        elif bool(exec_context.get("is_fallback", False)):
            is_fb = True
        elif bool(exec_context.get("fallback_used", False)):
            has_specific_targets = (
                bool(exec_context.get("fallback_step_ids"))
                or bool(exec_context.get("fallback_step_indices"))
                or bool(exec_context.get("fallback_actions"))
            )
            if not has_specific_targets:
                is_fb = True

        primary = (
            getattr(step_obj, "primary_strategy", None)
            or exec_context.get("primary_strategies", {}).get(s_id)
            or exec_context.get("primary_strategies", {}).get(a_type)
            or exec_context.get("primary_strategy")
        )
        if not primary and isinstance(exec_context.get("automation_plan"), dict):
            for ps in exec_context["automation_plan"].get("steps", []):
                if (s_id and ps.get("step_id") == s_id) or (ps.get("action") == a_type):
                    fb_strat = ps.get("fallback_strategy")
                    if fb_strat and str(fb_strat).upper() == strat.upper():
                        primary = ps.get("selected_strategy")
                        is_fb = True
                    break

        return is_fb, str(primary).upper() if primary else None

    # Resolve each step from step_results or actions_detail or results
    if step_results:
        for idx, sr in enumerate(step_results):
            s_id = sr.step_id or f"step_{idx+1}"
            a_type = sr.action_type or "unknown_action"
            app = "workflow_system"
            if idx < len(actions_detail):
                app = actions_detail[idx].get("application", app)

            strat = _infer_strategy_for_step(
                action_type=a_type,
                application=app,
                executor_type=execution.executor_type,
                context=exec_context,
                step_id=s_id,
            )

            is_fb, primary_strat = _resolve_step_fallback(s_id, a_type, idx, strat, sr)
            if is_fb:
                fallback_used = True

            sr_status_lower = (sr.status or "").lower()
            if sr_status_lower == "completed":
                step_stat = ExecutionOutcomeStatus.SUCCESS
                fail_cat = None
                err_msg = None
            elif sr_status_lower == "failed":
                step_stat = ExecutionOutcomeStatus.FAILED
                failed_steps_count += 1
                fail_cat = categorize_failure(sr.error) if sr.error else FailureCategory.UNKNOWN
                err_msg = sanitize_log_message(sr.error) if sr.error else None
            elif sr_status_lower == "paused" or overall_status == ExecutionOutcomeStatus.PAUSED:
                step_stat = ExecutionOutcomeStatus.PAUSED
                fail_cat = None
                err_msg = None
            elif sr_status_lower == "cancelled" or overall_status == ExecutionOutcomeStatus.CANCELLED:
                step_stat = ExecutionOutcomeStatus.CANCELLED
                fail_cat = None
                err_msg = None
            elif sr_status_lower in ("pending", "skipped", "not_started", "unexecuted"):
                step_stat = ExecutionOutcomeStatus.NOT_EXECUTED
                fail_cat = None
                err_msg = None
            else:
                if sr.error and overall_status in (ExecutionOutcomeStatus.FAILED, ExecutionOutcomeStatus.PARTIAL):
                    step_stat = ExecutionOutcomeStatus.FAILED
                    failed_steps_count += 1
                    fail_cat = categorize_failure(sr.error)
                    err_msg = sanitize_log_message(sr.error)
                else:
                    step_stat = ExecutionOutcomeStatus.NOT_EXECUTED
                    fail_cat = None
                    err_msg = None

            # Calculate duration if timestamps or duration_seconds are present
            dur_sec = getattr(sr, "duration_seconds", None)
            if dur_sec is None and getattr(sr, "started_at", None) and getattr(sr, "completed_at", None):
                try:
                    s_dt = datetime.fromisoformat(sr.started_at.replace("Z", "+00:00"))
                    c_dt = datetime.fromisoformat(sr.completed_at.replace("Z", "+00:00"))
                    dur_sec = round((c_dt - s_dt).total_seconds(), 3)
                except Exception:
                    dur_sec = None

            attempts_val = getattr(sr, "attempts", 1) or 1
            retries_cnt = getattr(sr, "retry_attempts", None)
            if retries_cnt is None:
                retries_cnt = max(0, attempts_val - 1)

            step_outcomes.append(
                StepOutcome(
                    step_id=s_id,
                    action=a_type,
                    application=app,
                    strategy=strat,
                    status=step_stat,
                    duration_seconds=dur_sec,
                    retries=retries_cnt,
                    is_fallback=is_fb,
                    primary_strategy=primary_strat,
                    failure_category=fail_cat,
                    error_message=err_msg,
                )
            )
    elif results_list:
        for idx, r in enumerate(results_list):
            s_id = r.action_id or f"step_{idx+1}"
            a_type = r.action_type
            app = next(
                (d.get("application", "workflow_system") for d in actions_detail if d.get("action") == a_type),
                "workflow_system"
            )

            strat = _infer_strategy_for_step(
                action_type=a_type,
                application=app,
                executor_type=execution.executor_type,
                context=exec_context,
                step_id=s_id,
            )

            is_fb, primary_strat = _resolve_step_fallback(s_id, a_type, idx, strat, r)
            if is_fb:
                fallback_used = True

            if r.success:
                step_stat = ExecutionOutcomeStatus.SUCCESS
                fail_cat = None
                err_msg = None
            else:
                if overall_status == ExecutionOutcomeStatus.PAUSED:
                    step_stat = ExecutionOutcomeStatus.PAUSED
                    fail_cat = None
                    err_msg = None
                elif overall_status == ExecutionOutcomeStatus.CANCELLED:
                    step_stat = ExecutionOutcomeStatus.CANCELLED
                    fail_cat = None
                    err_msg = None
                else:
                    step_stat = ExecutionOutcomeStatus.FAILED
                    failed_steps_count += 1
                    fail_cat = categorize_failure(r.message)
                    err_msg = sanitize_log_message(r.message) if r.message else None

            step_outcomes.append(
                StepOutcome(
                    step_id=s_id,
                    action=a_type,
                    application=app,
                    strategy=strat,
                    status=step_stat,
                    duration_seconds=None,
                    retries=0,
                    is_fallback=is_fb,
                    primary_strategy=primary_strat,
                    failure_category=fail_cat,
                    error_message=err_msg,
                )
            )

    # Capture unexecuted actions declared in actions_detail
    executed_ids = {so.step_id for so in step_outcomes}
    for idx, act in enumerate(actions_detail):
        act_id = act.get("step_id") or act.get("id") or f"step_{idx+1}"
        if act_id in executed_ids:
            continue
        act_action = act.get("action") or act.get("type") or "unknown_action"
        app = act.get("application", "workflow_system")
        strat = _infer_strategy_for_step(
            action_type=act_action,
            application=app,
            executor_type=execution.executor_type,
            context=exec_context,
            step_id=act_id,
        )
        if overall_status == ExecutionOutcomeStatus.PAUSED:
            unexec_stat = ExecutionOutcomeStatus.PAUSED
        elif overall_status == ExecutionOutcomeStatus.CANCELLED:
            unexec_stat = ExecutionOutcomeStatus.CANCELLED
        else:
            unexec_stat = ExecutionOutcomeStatus.NOT_EXECUTED

        step_outcomes.append(
            StepOutcome(
                step_id=act_id,
                action=act_action,
                application=app,
                strategy=strat,
                status=unexec_stat,
                duration_seconds=None,
                retries=0,
                is_fallback=False,
                primary_strategy=None,
                failure_category=None,
                error_message=None,
            )
        )

    unexecuted_count = sum(
        1 for so in step_outcomes
        if so.status in (
            ExecutionOutcomeStatus.PAUSED,
            ExecutionOutcomeStatus.CANCELLED,
            ExecutionOutcomeStatus.NOT_EXECUTED,
        )
    )
    if total_steps > len(step_outcomes):
        unexecuted_count += (total_steps - len(step_outcomes))

    # Identify failed step and overall failure category (only from genuinely failed steps)
    failed_step = None
    if overall_status in (ExecutionOutcomeStatus.FAILED, ExecutionOutcomeStatus.PARTIAL):
        failed_step = execution.failed_action
        if not failed_step and step_outcomes:
            for so in step_outcomes:
                if so.status == ExecutionOutcomeStatus.FAILED:
                    failed_step = so.action
                    break

    raw_err = execution.failure_reason or execution.error
    overall_failure_cat = None
    if overall_status in (ExecutionOutcomeStatus.FAILED, ExecutionOutcomeStatus.PARTIAL):
        if raw_err:
            overall_failure_cat = categorize_failure(raw_err)
        if not overall_failure_cat and step_outcomes:
            for so in step_outcomes:
                if so.failure_category:
                    overall_failure_cat = so.failure_category
                    break

    now_iso = datetime.now(timezone.utc).isoformat()
    return WorkflowExecutionOutcome(
        workflow_id=resolved_id,
        execution_id=execution.execution_id,
        status=overall_status,
        started_at=execution.started_at or now_iso,
        completed_at=execution.completed_at,
        duration_seconds=execution.execution_time_seconds,
        total_steps=total_steps,
        completed_steps=completed_count if completed_count > 0 else sum(1 for so in step_outcomes if so.status == ExecutionOutcomeStatus.SUCCESS),
        failed_steps_count=failed_steps_count,
        unexecuted_steps_count=unexecuted_count,
        failed_step=failed_step,
        failure_category=overall_failure_cat,
        fallback_used=fallback_used,
        step_outcomes=step_outcomes,
        error_message=sanitize_log_message(raw_err) if (overall_status in (ExecutionOutcomeStatus.FAILED, ExecutionOutcomeStatus.PARTIAL) and raw_err) else None,
    )



# ---------------------------------------------------------------------------
# Phase 9 Backward-Compatible Signal Extractor
# ---------------------------------------------------------------------------

class ExecutionLearningOutcome(BaseModel):
    """
    Interpreted execution signals extracted from an AutomationExecution (Phase 9 compat).
    """
    workflow_id: str = Field(..., description="Canonical target workflow ID")
    execution_id: str = Field(..., description="Execution ID")
    status: str = Field(..., description="Lifecycle status: completed, paused, failed, cancelled")
    is_completed: bool = Field(default=False, description="Whether execution finished successfully")
    is_failed: bool = Field(default=False, description="Whether execution failed terminally")
    requires_intervention: bool = Field(default=False, description="Whether human intervention was requested")
    is_recovery: bool = Field(default=False, description="Whether execution was resumed or recovered")
    failed_step: Optional[str] = Field(default=None, description="Step action type that failed")
    failure_reason: Optional[str] = Field(default=None, description="Sanitized failure reason")


def interpret_execution_outcome(
    execution: AutomationExecution,
    target_workflow_id: Optional[str] = None,
) -> Optional[ExecutionLearningOutcome]:
    """
    Phase 9 backward-compatible outcome interpreter.
    """
    if execution.status in (AutomationStatus.PENDING, AutomationStatus.RUNNING):
        return None

    resolved_id = target_workflow_id or execution.workflow_id
    if not resolved_id:
        if execution.workflow_name:
            slug = re.sub(r"[^a-zA-Z0-9_]+", "_", execution.workflow_name.strip().lower())
            resolved_id = f"wf_{slug}"
        else:
            resolved_id = "wf_unknown"

    is_completed = (execution.status == AutomationStatus.COMPLETED)
    is_failed = (execution.status == AutomationStatus.FAILED)
    requires_intervention = (
        execution.requires_human_intervention
        or execution.status == AutomationStatus.PAUSED
    )
    is_recovery = (
        (execution.recovery_attempts is not None and execution.recovery_attempts > 0)
        or (execution.resume_count is not None and execution.resume_count > 0)
    )

    failed_step = execution.failed_action or execution.current_action
    if not failed_step and execution.step_results:
        for sr in execution.step_results:
            if sr.status == "failed":
                failed_step = sr.action_type or sr.step_id
                break

    raw_reason = execution.failure_reason or execution.error
    sanitized_reason = sanitize_log_message(raw_reason) if raw_reason else None

    return ExecutionLearningOutcome(
        workflow_id=resolved_id,
        execution_id=execution.execution_id,
        status=str(execution.status.value if hasattr(execution.status, "value") else execution.status),
        is_completed=is_completed,
        is_failed=is_failed,
        requires_intervention=requires_intervention,
        is_recovery=is_recovery,
        failed_step=failed_step,
        failure_reason=sanitized_reason,
    )
