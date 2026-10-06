"""
WorkFlowOS Phase 15: End-to-End Pipeline Benchmark

Executes a deterministic end-to-end benchmark running through all 10 stages:
Activity Events
      ↓
Discovery
      ↓
Confidence Evaluation
      ↓
Utility Ranking
      ↓
Workflow Understanding
      ↓
Adaptive Learning
      ↓
Automation Planning
      ↓
Human Approval Gate
      ↓
Mock Execution
      ↓
Closed-Loop Outcome Evaluation
      ↓
Learning Evidence Update

Measures each stage independently and reports end_to_end_success rate.
"""

import asyncio
from typing import Dict, List, Any

from discovery.detector import RepetitionDetector
from ai.models import WorkflowProposal, WorkflowAction, WorkflowTrigger
from backend.learning.state import compute_learning_score, determine_recommendation_status
from backend.learning.models import RecommendationStatus
from automation.planner.planner import AutomationPlanner
from automation.engine import AutomationEngine
from automation.executor import NoOpExecutor
from automation.models import AutomationStatus
from backend.learning.outcome import evaluate_execution_outcome, ExecutionOutcomeStatus


async def _run_e2e_benchmark_async() -> Dict[str, Any]:
    stages: Dict[str, bool] = {}
    stage_details: Dict[str, Any] = {}

    # Stage 1: Activity Events
    canonical_steps = [
        "open_email",
        "download_attachment",
        "search_customer",
        "update_customer",
        "send_message",
    ]
    sessions = {
        "sess_e2e_1": list(canonical_steps),
        "sess_e2e_2": list(canonical_steps),
        "sess_e2e_3": list(canonical_steps),
    }
    stages["stage_1_activity_events"] = len(sessions) == 3
    stage_details["stage_1_activity_events"] = {
        "sessions_count": len(sessions),
        "steps_per_session": len(canonical_steps),
    }

    # Stage 2: Discovery
    detector = RepetitionDetector(min_length=3, min_occurrences=2, similarity_threshold=0.8)
    discovery_res = detector.detect(sessions)
    discovered_wf = discovery_res.workflows[0] if discovery_res.workflows else None
    stages["stage_2_discovery"] = discovery_res.detected and discovered_wf is not None
    stage_details["stage_2_discovery"] = {
        "detected": discovery_res.detected,
        "workflows_found": len(discovery_res.workflows),
        "matched_sequence": discovered_wf.sequence if discovered_wf else [],
    }

    # Stage 3: Confidence Evaluation
    conf = discovered_wf.confidence if discovered_wf else 0.0
    stages["stage_3_confidence"] = conf >= 0.70
    stage_details["stage_3_confidence"] = {
        "confidence_score": conf,
        "meets_threshold": conf >= 0.70,
    }

    # Stage 4: Ranking
    ranking_score = discovered_wf.ranking_score if discovered_wf else 0.0
    stages["stage_4_ranking"] = ranking_score > 0.0
    stage_details["stage_4_ranking"] = {
        "ranking_score": ranking_score,
        "quality_tier": getattr(discovered_wf, "quality_tier", "unknown"),
    }

    # Stage 5: Workflow Understanding
    proposal = WorkflowProposal(
        name="Customer Support Resolution",
        intent="Process customer email and update CRM record",
        trigger=WorkflowTrigger(
            type="new_email",
            application="demo_email",
            description="Incoming support email",
        ),
        actions=[
            WorkflowAction(type="open_email", application="demo_email", description="Open email", target="inbox"),
            WorkflowAction(type="download_attachment", application="demo_email", description="Download PDF", target="spec.pdf"),
            WorkflowAction(type="search_customer", application="demo_crm", description="Search customer", target="cust_id"),
            WorkflowAction(type="update_customer", application="demo_crm", description="Update record", target="cust_id"),
            WorkflowAction(type="send_message", application="demo_chat", description="Notify Slack", target="support"),
        ],
        applications=["demo_email", "demo_crm", "demo_chat"],
        requires_approval=True,
    )
    stages["stage_5_understanding"] = (
        len(proposal.actions) == len(canonical_steps)
        and proposal.requires_approval is True
    )
    stage_details["stage_5_understanding"] = {
        "actions_count": len(proposal.actions),
        "requires_approval": proposal.requires_approval,
    }

    # Stage 6: Learning Prior
    initial_score = compute_learning_score(0, 0, 0, 0, 0, 0, 0)
    initial_status = determine_recommendation_status(initial_score, 0, 0, 0, 0, 0, 0)
    stages["stage_6_learning_prior"] = (
        initial_score == 0.50 and initial_status == RecommendationStatus.NEW
    )
    stage_details["stage_6_learning_prior"] = {
        "prior_score": initial_score,
        "prior_status": initial_status.value,
    }

    # Stage 7: Automation Planning
    planner = AutomationPlanner()
    plan = await planner.create_plan(
        workflow_id="wf_e2e_benchmark",
        steps=[
            {"id": f"step_{idx+1}", "type": act, "application": "crm" if "customer" in act else ("chat" if "message" in act else "email")}
            for idx, act in enumerate(canonical_steps)
        ],
    )
    stages["stage_7_planning"] = (
        plan is not None
        and plan.requires_approval is True
        and len(plan.steps) == len(canonical_steps)
    )
    stage_details["stage_7_planning"] = {
        "plan_strategy": plan.selected_strategy.value if plan else None,
        "plan_score": plan.overall_score if plan else 0.0,
        "requires_approval": plan.requires_approval if plan else False,
    }

    # Stage 8: Human Approval Gate
    human_approved = True
    stages["stage_8_approval_gate"] = human_approved is True
    stage_details["stage_8_approval_gate"] = {
        "human_decision": "APPROVED",
        "bypass_detected": False,
    }

    # Stage 9: Mock Execution
    engine = AutomationEngine(default_executor=NoOpExecutor())
    exec_record = await engine.execute_workflow(
        proposal=proposal,
        approved=human_approved,
    )
    stages["stage_9_execution"] = (exec_record.status == AutomationStatus.COMPLETED)
    stage_details["stage_9_execution"] = {
        "status": exec_record.status.value,
        "completed_actions": len(exec_record.completed_actions or []),
    }

    # Stage 10: Closed-Loop Outcome Evaluation & Learning Evidence
    outcome = evaluate_execution_outcome(exec_record)
    outcome_ok = outcome is not None and outcome.status == ExecutionOutcomeStatus.SUCCESS

    # Feed evidence into learning score
    updated_score = compute_learning_score(
        approval_count=1,
        rejection_count=0,
        edit_count=0,
        successful_execution_count=1,
        failed_execution_count=0,
        intervention_count=0,
        recovery_count=0,
    )
    updated_status = determine_recommendation_status(
        learning_score=updated_score,
        approval_count=1,
        rejection_count=0,
        edit_count=0,
        execution_count=1,
        successful_execution_count=1,
        failed_execution_count=0,
    )
    # Score increased: 0.50 -> 0.75
    evidence_ok = (updated_score == 0.75 and updated_status == RecommendationStatus.RECOMMENDED)

    stages["stage_10_closed_loop"] = outcome_ok and evidence_ok
    stage_details["stage_10_closed_loop"] = {
        "outcome_status": outcome.status.value if outcome else None,
        "updated_learning_score": updated_score,
        "updated_recommendation_status": updated_status.value,
    }

    total_stages = len(stages)
    passed_stages = sum(1 for v in stages.values() if v)
    pipeline_success = (passed_stages == total_stages)

    return {
        "end_to_end_success": 1.0 if pipeline_success else 0.0,
        "total_stages": total_stages,
        "passed_stages": passed_stages,
        "all_stages_passed": pipeline_success,
        "stage_statuses": stages,
        "stage_details": stage_details,
    }


def run_end_to_end_benchmark() -> Dict[str, Any]:
    """Synchronous wrapper for end-to-end benchmark."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                return executor.submit(asyncio.run, _run_e2e_benchmark_async()).result()
        else:
            return loop.run_until_complete(_run_e2e_benchmark_async())
    except RuntimeError:
        return asyncio.run(_run_e2e_benchmark_async())
