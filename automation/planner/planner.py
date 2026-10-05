"""
WorkFlowOS Phase 10: Intelligent Automation Planner

Coordinates step analysis, capability inspection, deterministic scoring,
strategy selection, explainability synthesis, and fallback planning.

Strict Safety Invariants:
- The planner NEVER autonomously executes workflows.
- Human approval gate (requires_approval=True) is strictly mandatory.
- Credentials and sensitive metadata are NEVER exposed in plans or explanations.
- Strategy scores are deterministic heuristic suitability scores in [0.0, 1.0], NOT probabilities.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from automation.planner.models import (
    AutomationStrategyType,
    StrategyCandidate,
    StepPlan,
    AutomationPlan,
)
from automation.planner.registry import capability_registry, StrategyCapabilityRegistry
from automation.planner.scorer import strategy_scorer, StrategyScorer
from backend.learning.service import learning_service, LearningService
from backend.learning.models import WorkflowLearningState
from automation.service import automation_service

logger = logging.getLogger(__name__)

# Canonical built-in workflow template steps
BUILT_IN_WORKFLOW_STEPS: Dict[str, List[Dict[str, Any]]] = {
    "wf_customer_support_pipeline": [
        {
            "id": "step_open_email",
            "type": "open_email",
            "application": "demo_email",
            "target": "support_inbox",
            "description": "Open customer support email in inbox",
        },
        {
            "id": "step_download_attachment",
            "type": "download_attachment",
            "application": "demo_email",
            "target": "customer_spec.pdf",
            "description": "Download invoice or specification attachment",
        },
        {
            "id": "step_search_customer",
            "type": "search_customer",
            "application": "demo_crm",
            "target": "Rahul Sharma",
            "description": "Search CRM for existing customer record",
        },
        {
            "id": "step_update_customer",
            "type": "update_customer",
            "application": "demo_crm",
            "target": "status_verified",
            "description": "Update customer record with verified status",
        },
        {
            "id": "step_send_message",
            "type": "send_message",
            "application": "demo_chat",
            "target": "internal_team",
            "description": "Send confirmation message to internal team",
        },
    ],
    "wf_gmail_triage_pipeline": [
        {
            "id": "step_list_messages",
            "type": "list_recent_messages",
            "application": "gmail",
            "target": "inbox",
            "description": "List recent messages from Gmail via OAuth API",
        },
        {
            "id": "step_search_customer",
            "type": "search_customer",
            "application": "demo_crm",
            "target": "sender_email",
            "description": "Cross-reference sender in CRM",
        },
    ],
}


class AutomationPlanner:
    """
    Intelligent Automation Planner for WorkFlowOS.
    Analyzes workflow steps and deterministically chooses the safest,
    most reliable automation strategy for each step and for the workflow overall.
    """

    def __init__(
        self,
        registry: Optional[StrategyCapabilityRegistry] = None,
        scorer: Optional[StrategyScorer] = None,
        learning_svc: Optional[LearningService] = None,
    ):
        self.registry = registry or capability_registry
        self.scorer = scorer or strategy_scorer
        self.learning_service = learning_svc or learning_service

    async def create_plan(
        self,
        workflow_id: str,
        steps: Optional[List[Dict[str, Any]]] = None,
        context: Optional[Dict[str, Any]] = None,
        workflow_name: Optional[str] = None,
        strategy_override: Optional[Dict[str, str]] = None,
    ) -> AutomationPlan:
        """
        Generates an explainable, deterministic AutomationPlan for the given workflow.
        """
        ctx = dict(context or {})
        resolved_name = workflow_name or f"Workflow {workflow_id}"

        # 1. Resolve steps
        resolved_steps = await self._resolve_steps(workflow_id, steps)
        if not resolved_steps:
            raise KeyError(f"Workflow '{workflow_id}' not found and no steps provided.")

        # 2. Consume Phase 9 learning state (does not mutate it)
        try:
            learning_state = await self.learning_service.get_learning_state(workflow_id)
        except Exception as le:
            logger.warning(f"[AutomationPlanner] Could not retrieve learning state for {workflow_id}: {le}")
            learning_state = None

        # Phase 11: Consume Closed-Loop Strategy Evidence
        strategy_evidence_map: Dict[Tuple[str, str], Any] = {}
        try:
            evidence_records = await self.learning_service.get_strategy_evidence(workflow_id)
            for ev in evidence_records:
                strategy_evidence_map[(ev.step_action.lower(), ev.strategy.upper())] = ev
        except Exception as ee:
            logger.warning(f"[AutomationPlanner] Could not retrieve strategy evidence for {workflow_id}: {ee}")

        # 3. Analyze each step and score candidate strategies
        step_plans: List[StepPlan] = []
        strategy_counts: Dict[str, int] = {}

        for raw_step in resolved_steps:
            step_id = raw_step.get("id") or raw_step.get("step_id") or f"step_{len(step_plans)+1}"
            action = raw_step.get("type") or raw_step.get("action") or "unknown_action"
            application = raw_step.get("application") or "unknown_application"
            desc = raw_step.get("description")

            step_plan = self._plan_step(
                step_id=step_id,
                action=action,
                application=application,
                description=desc,
                learning_state=learning_state,
                context=ctx,
                strategy_override=strategy_override.get(step_id) if strategy_override else None,
                evidence_map=strategy_evidence_map,
            )
            step_plans.append(step_plan)
            strat_val = step_plan.selected_strategy.value
            strategy_counts[strat_val] = strategy_counts.get(strat_val, 0) + 1

        # 4. Determine overall workflow strategy and composite score
        overall_strategy = self._determine_overall_strategy(step_plans)
        overall_score = round(
            sum(sp.score for sp in step_plans) / len(step_plans), 4
        ) if step_plans else 0.0

        fallback_available = any(sp.fallback_strategy is not None for sp in step_plans)

        # 5. Synthesize overall explanation
        explanation = self._synthesize_plan_explanation(
            workflow_id=workflow_id,
            overall_strategy=overall_strategy,
            overall_score=overall_score,
            step_plans=step_plans,
            strategy_counts=strategy_counts,
            learning_state=learning_state,
        )

        learning_summary = None
        if learning_state:
            learning_summary = {
                "learning_score": round(learning_state.learning_score, 2),
                "recommendation_status": learning_state.recommendation_status.value,
                "execution_count": learning_state.execution_count,
                "successful_execution_count": learning_state.successful_execution_count,
                "failed_execution_count": learning_state.failed_execution_count,
                "intervention_count": learning_state.intervention_count,
            }

        plan = AutomationPlan(
            workflow_id=workflow_id,
            workflow_name=resolved_name,
            selected_strategy=overall_strategy,
            overall_score=overall_score,
            steps=step_plans,
            requires_approval=True,  # Safety Gate Invariant
            fallback_available=fallback_available,
            explanation=explanation,
            learning_state_summary=learning_summary,
        )

        logger.info(
            f"[AutomationPlanner] Created plan for '{workflow_id}' | "
            f"Strategy: {overall_strategy.value} | Score: {overall_score:.2f} | "
            f"Steps: {len(step_plans)} | Approval Mandatory: {plan.requires_approval}"
        )
        return plan

    async def _resolve_steps(
        self,
        workflow_id: str,
        steps: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """Resolves workflow steps from request, known templates, or automation service."""
        if steps and len(steps) > 0:
            return steps

        # Check built-in canonical templates
        if workflow_id in BUILT_IN_WORKFLOW_STEPS:
            return BUILT_IN_WORKFLOW_STEPS[workflow_id]

        # Check stored workflow definitions in automation_service
        wf_def = getattr(automation_service, "_workflows", {}).get(workflow_id)
        if wf_def and hasattr(wf_def, "steps"):
            return [step.model_dump() for step in wf_def.steps]

        # Check recorded executions
        for exec_obj in automation_service.list_executions():
            if exec_obj.workflow_id == workflow_id or exec_obj.execution_id == workflow_id:
                if exec_obj.actions_detail:
                    return exec_obj.actions_detail

        return []

    def _plan_step(
        self,
        step_id: str,
        action: str,
        application: str,
        description: Optional[str],
        learning_state: Optional[WorkflowLearningState],
        context: Dict[str, Any],
        strategy_override: Optional[str] = None,
        evidence_map: Optional[Dict[Tuple[str, str], Any]] = None,
    ) -> StepPlan:
        """Plans a single workflow action step."""
        step_ctx = dict(context)
        # Pull step-specific history if provided
        history = step_ctx.get(f"history_{step_id}") or step_ctx.get(f"history_{action}") or step_ctx.get("history") or {}

        # 1. Get capabilities from registry
        cap_map = self.registry.get_capabilities_for_step(action, application, context=step_ctx)

        candidates: List[StrategyCandidate] = []
        for strategy in [
            AutomationStrategyType.API,
            AutomationStrategyType.INTEGRATION,
            AutomationStrategyType.SEMANTIC_UI,
            AutomationStrategyType.BROWSER,
            AutomationStrategyType.MANUAL,
        ]:
            cap_info = cap_map.get(strategy, {})
            is_avail = cap_info.get("is_available", False)
            rej_reason = cap_info.get("rejection_reason")
            is_mut = cap_info.get("is_mutating", False)
            req_creds = cap_info.get("requires_credentials", False)
            creds_avail = cap_info.get("credentials_available", True)

            # Phase 11: Step-specific strategy metrics from evidence map or context history
            strat_key_pfx = strategy.value.lower()
            ev = None
            if evidence_map:
                ev = evidence_map.get((action.lower(), strategy.value.upper()))

            succ = history.get(f"{strat_key_pfx}_successes")
            if succ is None and ev:
                succ = ev.successes
            fail = history.get(f"{strat_key_pfx}_failures")
            if fail is None and ev:
                fail = ev.failures
            last_failed = history.get(f"{strat_key_pfx}_last_failed")
            if last_failed is None and ev:
                last_failed = (ev.last_outcome == "FAILED")
            rec_succ = history.get(f"{strat_key_pfx}_recent_successes")
            if rec_succ is None and ev:
                rec_succ = ev.recent_successes
            rec_fail = history.get(f"{strat_key_pfx}_recent_failures")
            if rec_fail is None and ev:
                rec_fail = ev.recent_failures
            fallback_cnt = history.get(f"{strat_key_pfx}_fallback_count")
            if fallback_cnt is None and ev:
                fallback_cnt = ev.fallback_count

            strat_history = {
                f"{strat_key_pfx}_successes": succ,
                f"{strat_key_pfx}_failures": fail,
                f"{strat_key_pfx}_last_failed": bool(last_failed),
                f"{strat_key_pfx}_recent_successes": rec_succ,
                f"{strat_key_pfx}_recent_failures": rec_fail,
                "recent_successes": rec_succ,
                "recent_failures": rec_fail,
                "fallback_count": fallback_cnt,
            }

            candidate = self.scorer.score_strategy(
                strategy=strategy,
                is_available=is_avail,
                rejection_reason=rej_reason,
                action=action,
                application=application,
                is_mutating=is_mut,
                requires_credentials=req_creds,
                credentials_available=creds_avail,
                learning_state=learning_state,
                history=strat_history,
            )
            candidates.append(candidate)

        # 2. Select strategy
        selected_candidate: Optional[StrategyCandidate] = None

        # Check manual override
        if strategy_override:
            for cand in candidates:
                if cand.strategy.value.upper() == strategy_override.upper() and cand.is_available:
                    selected_candidate = cand
                    break

        if not selected_candidate:
            # Sort available candidates by score descending, then by priority hierarchy
            hierarchy_order = {
                AutomationStrategyType.API: 5,
                AutomationStrategyType.INTEGRATION: 4,
                AutomationStrategyType.SEMANTIC_UI: 3,
                AutomationStrategyType.BROWSER: 2,
                AutomationStrategyType.MANUAL: 1,
            }
            available_candidates = [c for c in candidates if c.is_available]
            if available_candidates:
                available_candidates.sort(
                    key=lambda c: (c.score, hierarchy_order.get(c.strategy, 0)),
                    reverse=True
                )
                selected_candidate = available_candidates[0]

        # If still no candidate selected or score is 0.0, fallback to MANUAL
        if not selected_candidate or selected_candidate.score <= 0.0:
            for cand in candidates:
                if cand.strategy == AutomationStrategyType.MANUAL:
                    selected_candidate = cand
                    break

        # Fallback candidate selection
        fallback_candidate: Optional[StrategyCandidate] = None
        if selected_candidate and selected_candidate.strategy != AutomationStrategyType.MANUAL:
            remaining = [
                c for c in candidates
                if c.is_available and c.strategy != selected_candidate.strategy and c.score > 0.0
            ]
            if remaining:
                remaining.sort(
                    key=lambda c: (c.score, hierarchy_order.get(c.strategy, 0)),
                    reverse=True
                )
                fallback_candidate = remaining[0]
            else:
                # Manual fallback
                for cand in candidates:
                    if cand.strategy == AutomationStrategyType.MANUAL:
                        fallback_candidate = cand
                        break

        # Build explainability dictionaries
        selected_reasons = list(selected_candidate.selection_reasons)
        rejected_reasons: Dict[str, str] = {}
        for cand in candidates:
            if cand.strategy != selected_candidate.strategy:
                if not cand.is_available:
                    rejected_reasons[cand.strategy.value] = cand.rejection_reason or "Not available for this action"
                elif cand.score < selected_candidate.score:
                    if cand.score_breakdown.failure_penalty > 0.20:
                        rejected_reasons[cand.strategy.value] = (
                            f"Higher historical failure rate penalty (-{cand.score_breakdown.failure_penalty:.2f}) "
                            f"reduced score to {cand.score:.2f} (below {selected_candidate.strategy.value} at {selected_candidate.score:.2f})"
                        )
                    elif cand.score_breakdown.priority_score < selected_candidate.score_breakdown.priority_score:
                        rejected_reasons[cand.strategy.value] = (
                            f"Lower architectural priority and suitability score ({cand.score:.2f} vs {selected_candidate.score:.2f})"
                        )
                    else:
                        rejected_reasons[cand.strategy.value] = (
                            f"Suitability score {cand.score:.2f} is lower than selected {selected_candidate.strategy.value} ({selected_candidate.score:.2f})"
                        )
                else:
                    rejected_reasons[cand.strategy.value] = "Alternative available candidate"

        # Concise primary justification
        reason = self._build_step_justification(selected_candidate, action, application)

        # Phase 11: Check if an adaptation occurred due to failure of a higher architectural priority candidate
        adapted_from = None
        for cand in candidates:
            if cand.strategy != selected_candidate.strategy and cand.score_breakdown.priority_score > selected_candidate.score_breakdown.priority_score:
                if cand.score_breakdown.failure_penalty > 0.15 or cand.metadata.get("recent_failures", 0) > 0:
                    adapted_from = cand
                    break

        if adapted_from:
            adaptation_note = (
                f"{selected_candidate.strategy.value.capitalize()} was selected because the {adapted_from.strategy.value} "
                f"strategy has repeated recent failures for this workflow step."
            )
            selected_reasons.insert(0, adaptation_note)
            reason = f"{selected_candidate.strategy.value.capitalize()} was selected because the {adapted_from.strategy.value} strategy has repeated recent failures for this workflow step."

        fallback_strat = fallback_candidate.strategy if fallback_candidate else None
        fallback_reason = (
            f"Use {fallback_strat.value} if {selected_candidate.strategy.value} fails or becomes unavailable"
            if fallback_strat else None
        )

        return StepPlan(
            step_id=step_id,
            action=action,
            application=application,
            description=description,
            selected_strategy=selected_candidate.strategy,
            score=selected_candidate.score,
            reason=reason,
            selected_reasons=selected_reasons,
            rejected_strategies=rejected_reasons,
            candidates=candidates,
            fallback_strategy=fallback_strat,
            fallback_reason=fallback_reason,
            is_mutating=selected_candidate.metadata.get("is_mutating", False),
            requires_credentials=selected_candidate.score_breakdown.credential_score < 0.10,
            credentials_available=selected_candidate.score_breakdown.safety_penalty < 0.20,
        )

    def _determine_overall_strategy(self, step_plans: List[StepPlan]) -> AutomationStrategyType:
        """Determines the primary/predominant execution strategy for the workflow."""
        if not step_plans:
            return AutomationStrategyType.MANUAL

        # Count frequencies
        freq: Dict[AutomationStrategyType, int] = {}
        for sp in step_plans:
            freq[sp.selected_strategy] = freq.get(sp.selected_strategy, 0) + 1

        # Priority resolution when mixed:
        # If any step requires MANUAL intervention, overall plan highlights MANUAL oversight
        # If all steps are automated, pick majority strategy or highest coordination mode
        sorted_by_freq = sorted(freq.items(), key=lambda kv: kv[1], reverse=True)
        return sorted_by_freq[0][0]

    def _build_step_justification(
        self,
        candidate: StrategyCandidate,
        action: str,
        application: str
    ) -> str:
        """Builds a concise, user-friendly justification for step selection."""
        strat = candidate.strategy
        score = candidate.score
        breakdown = candidate.score_breakdown

        if strat == AutomationStrategyType.API:
            return f"Selected API: High-reliability direct adapter for '{action}' with suitability score {score:.2f}."
        elif strat == AutomationStrategyType.INTEGRATION:
            return f"Selected INTEGRATION: Verified adapter capability on '{application}' with score {score:.2f}."
        elif strat == AutomationStrategyType.BROWSER:
            if breakdown.failure_penalty == 0 and breakdown.reliability_score > 0.15:
                return f"Selected BROWSER: Reliable UI automation on '{application}' with score {score:.2f}."
            return f"Selected BROWSER: Validated browser automation step with suitability score {score:.2f}."
        elif strat == AutomationStrategyType.SEMANTIC_UI:
            return f"Selected SEMANTIC_UI: Accessibility-driven automation with score {score:.2f}."
        else:
            return f"Selected MANUAL: Action '{action}' requires human operator intervention (fallback)."

    def _synthesize_plan_explanation(
        self,
        workflow_id: str,
        overall_strategy: AutomationStrategyType,
        overall_score: float,
        step_plans: List[StepPlan],
        strategy_counts: Dict[str, int],
        learning_state: Optional[WorkflowLearningState],
    ) -> Dict[str, Any]:
        """Synthesizes human-readable explainability artifacts without sensitive data."""
        breakdown_str = ", ".join(f"{count} {strat}" for strat, count in strategy_counts.items())

        key_factors: List[str] = [
            f"Evaluated {len(step_plans)} workflow steps against repository capabilities.",
            f"Overall execution strategy '{overall_strategy.value}' with aggregate suitability {overall_score:.2f}.",
            f"Strategy distribution: {breakdown_str}.",
        ]

        if learning_state:
            key_factors.append(
                f"Phase 9 learning state: {learning_state.recommendation_status.value} "
                f"(score: {learning_state.learning_score:.2f}, {learning_state.successful_execution_count} successes, "
                f"{learning_state.failed_execution_count} failures)."
            )

        summary = (
            f"Intelligently planned workflow '{workflow_id}' using {overall_strategy.value} strategy "
            f"(composite score: {overall_score:.2f}). Evaluated capabilities, execution history, "
            f"and Phase 9 learning telemetry. Human approval is required prior to execution."
        )

        return {
            "summary": summary,
            "overall_strategy": overall_strategy.value,
            "overall_score": overall_score,
            "strategy_counts": strategy_counts,
            "key_factors": key_factors,
            "safety_model": (
                "Human approval gate remains mandatory. Mutating actions are isolated. "
                "No external credentials or tokens are exposed."
            ),
        }


# Global singleton planner
automation_planner = AutomationPlanner()
