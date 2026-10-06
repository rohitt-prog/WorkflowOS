"""
WorkFlowOS Phase 15: Automation Planner Benchmark

Evaluates Phase 10 Automation Planner strategy selection, heuristic scoring,
safe fallback behavior, and approval gate invariants without modifying production logic.

Validates strategy priority hierarchy:
API -> INTEGRATION -> SEMANTIC_UI -> BROWSER -> MANUAL
"""

import asyncio
from typing import Dict, List, Any

from automation.planner.planner import AutomationPlanner
from automation.planner.models import AutomationStrategyType, AutomationPlan, StepPlan


async def _run_planning_eval_async() -> Dict[str, Any]:
    planner = AutomationPlanner()

    test_workflows = [
        {
            "name": "Canonical Support Pipeline (API Priority Tier)",
            "workflow_id": "bench_wf_support",
            "context": {},
            "steps": [
                {
                    "id": "step_1",
                    "type": "open_email",
                    "application": "demo_email",
                    "description": "Open customer email via direct API",
                    "expected_strategy": AutomationStrategyType.API,
                },
                {
                    "id": "step_2",
                    "type": "download_attachment",
                    "application": "demo_email",
                    "description": "Download invoice PDF via browser capability",
                    "expected_strategy": AutomationStrategyType.BROWSER,
                },
                {
                    "id": "step_3",
                    "type": "search_customer",
                    "application": "demo_crm",
                    "description": "Lookup CRM profile via API",
                    "expected_strategy": AutomationStrategyType.API,
                },
                {
                    "id": "step_4",
                    "type": "update_customer",
                    "application": "demo_crm",
                    "description": "Update CRM record via API",
                    "expected_strategy": AutomationStrategyType.API,
                },
                {
                    "id": "step_5",
                    "type": "send_message",
                    "application": "demo_chat",
                    "description": "Post Slack notification via API",
                    "expected_strategy": AutomationStrategyType.API,
                },
            ],
            "expected_requires_approval": True,
        },
        {
            "name": "Integration Strategy Tier (API Disabled Context)",
            "workflow_id": "bench_wf_integration_tier",
            "context": {"api_available": False},
            "steps": [
                {
                    "id": "step_crm_int",
                    "type": "search_customer",
                    "application": "demo_crm",
                    "description": "Search customer via managed integration",
                    "expected_strategy": AutomationStrategyType.INTEGRATION,
                },
                {
                    "id": "step_chat_int",
                    "type": "send_message",
                    "application": "demo_chat",
                    "description": "Post chat notification via managed integration",
                    "expected_strategy": AutomationStrategyType.INTEGRATION,
                },
            ],
            "expected_requires_approval": True,
        },
        {
            "name": "Browser Strategy Tier (Web Only Action)",
            "workflow_id": "bench_wf_browser_tier",
            "context": {},
            "steps": [
                {
                    "id": "step_download_web",
                    "type": "download_attachment",
                    "application": "browser",
                    "description": "Download attachment from web portal",
                    "expected_strategy": AutomationStrategyType.BROWSER,
                }
            ],
            "expected_requires_approval": True,
        },
        {
            "name": "Universal Manual Fallback Tier (Unsupported Action)",
            "workflow_id": "bench_wf_manual_fallback",
            "context": {},
            "steps": [
                {
                    "id": "step_unknown",
                    "type": "unsupported_alien_action",
                    "application": "legacy_desktop_app",
                    "description": "Execute non-integrated command",
                    "expected_strategy": AutomationStrategyType.MANUAL,
                }
            ],
            "expected_requires_approval": True,
        },
    ]

    total_steps = 0
    correct_steps = 0
    safe_fallbacks_present = 0
    approval_enforced_count = 0
    step_eval_details: List[Dict[str, Any]] = []

    for tw in test_workflows:
        plan: AutomationPlan = await planner.create_plan(
            workflow_id=tw["workflow_id"],
            steps=tw["steps"],
            workflow_name=tw["name"],
            context=tw.get("context", {}),
        )

        if plan.requires_approval == tw["expected_requires_approval"]:
            approval_enforced_count += 1

        for idx, step_plan in enumerate(plan.steps):
            total_steps += 1
            expected_strat = tw["steps"][idx]["expected_strategy"]
            selected = step_plan.selected_strategy
            fallback = step_plan.fallback_strategy

            is_correct = (selected == expected_strat)
            if is_correct:
                correct_steps += 1

            if fallback is not None or selected == AutomationStrategyType.MANUAL:
                safe_fallbacks_present += 1

            step_eval_details.append({
                "workflow": tw["name"],
                "step_id": step_plan.step_id,
                "action": step_plan.action,
                "selected_strategy": selected.value,
                "expected_strategy": expected_strat.value,
                "score": step_plan.score,
                "fallback_strategy": fallback.value if fallback else None,
                "selection_reasons": step_plan.selected_reasons,
                "correct": is_correct,
            })

    strategy_selection_accuracy = round(correct_steps / total_steps, 4) if total_steps > 0 else 0.0
    fallback_safety_rate = round(safe_fallbacks_present / total_steps, 4) if total_steps > 0 else 0.0
    approval_enforcement_rate = round(approval_enforced_count / len(test_workflows), 4)

    return {
        "total_workflows_evaluated": len(test_workflows),
        "total_steps_evaluated": total_steps,
        "strategy_selection_accuracy": strategy_selection_accuracy,
        "fallback_safety_rate": fallback_safety_rate,
        "approval_enforcement_rate": approval_enforcement_rate,
        "zero_approval_bypass": approval_enforcement_rate == 1.0,
        "step_details": step_eval_details,
    }


def run_planning_benchmark() -> Dict[str, Any]:
    """Synchronous wrapper for planning benchmark."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                return executor.submit(asyncio.run, _run_planning_eval_async()).result()
        else:
            return loop.run_until_complete(_run_planning_eval_async())
    except RuntimeError:
        return asyncio.run(_run_planning_eval_async())
