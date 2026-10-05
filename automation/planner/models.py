"""
WorkFlowOS Phase 10: Intelligent Automation Models

Defines the core data models for the Intelligent Automation Planner:
- AutomationStrategyType (API, INTEGRATION, SEMANTIC_UI, BROWSER, MANUAL)
- StrategyScoreBreakdown (deterministic heuristic breakdown, NOT a probability)
- StrategyCandidate (per-strategy evaluation, availability, and audit reasons)
- StepPlan (per-action selected strategy, candidates, explanations, and fallback)
- AutomationPlan (complete workflow automation plan requiring human approval)
- API request and response envelopes
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class AutomationStrategyType(str, Enum):
    """
    Deterministic automation strategies recognized by WorkFlowOS.
    Conceptual priority hierarchy:
    API -> INTEGRATION -> SEMANTIC_UI -> BROWSER -> MANUAL
    """
    API = "API"
    INTEGRATION = "INTEGRATION"
    SEMANTIC_UI = "SEMANTIC_UI"
    BROWSER = "BROWSER"
    MANUAL = "MANUAL"


def _generate_plan_id() -> str:
    return f"plan_{uuid.uuid4().hex[:12]}"


def _current_iso_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


class StrategyScoreBreakdown(BaseModel):
    """
    Detailed breakdown of deterministic heuristic scoring factors.
    NOTE: Strategy scores are deterministic heuristic suitability scores in [0.0, 1.0],
    NOT statistical probabilities.
    """
    capability_score: float = Field(
        ...,
        ge=0.0,
        le=0.50,
        description="Action and application capability match score"
    )
    priority_score: float = Field(
        ...,
        ge=0.0,
        le=0.30,
        description="Architectural hierarchy baseline weight"
    )
    reliability_score: float = Field(
        ...,
        ge=0.0,
        le=0.30,
        description="Historical execution success rate contribution"
    )
    learning_score: float = Field(
        ...,
        ge=0.0,
        le=0.20,
        description="Phase 9 adaptive learning contribution"
    )
    credential_score: float = Field(
        ...,
        ge=0.0,
        le=0.15,
        description="Credential availability bonus"
    )
    failure_penalty: float = Field(
        default=0.0,
        ge=0.0,
        le=0.60,
        description="Deduction for historical failure rate and recent errors"
    )
    safety_penalty: float = Field(
        default=0.0,
        ge=0.0,
        le=0.50,
        description="Deduction for missing credentials, mutating risk, or unsafe channel"
    )
    raw_score: float = Field(
        ...,
        description="Unclamped sum of positive factors minus penalties"
    )
    final_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Normalized and clamped heuristic score in [0.0, 1.0]"
    )


class StrategyCandidate(BaseModel):
    """
    Represents an evaluated automation strategy candidate for a specific step.
    Includes availability status, score breakdown, and explainability notes.
    """
    strategy: AutomationStrategyType = Field(..., description="Strategy type")
    is_available: bool = Field(..., description="Whether this strategy is capable and available")
    score: float = Field(..., ge=0.0, le=1.0, description="Final heuristic suitability score")
    score_breakdown: StrategyScoreBreakdown = Field(..., description="Deterministic scoring component breakdown")
    selection_reasons: List[str] = Field(
        default_factory=list,
        description="Positive evidence supporting this strategy"
    )
    rejection_reason: Optional[str] = Field(
        default=None,
        description="Reason why this strategy was rejected or deemed unsuitable/unavailable"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Safe non-sensitive metadata (e.g. adapter name, mock flag, scopes)"
    )


class StepPlan(BaseModel):
    """
    The intelligent automation plan for a single workflow action step.
    """
    step_id: str = Field(..., description="Deterministic step identifier")
    action: str = Field(..., description="Action verb type (e.g. 'open_email', 'search_customer')")
    application: str = Field(..., description="Target application name")
    description: Optional[str] = Field(default=None, description="Human description of step")
    selected_strategy: AutomationStrategyType = Field(..., description="Best suitable strategy selected")
    score: float = Field(..., ge=0.0, le=1.0, description="Heuristic score of selected strategy")
    reason: str = Field(..., description="Primary user-facing justification for strategy selection")
    selected_reasons: List[str] = Field(
        default_factory=list,
        description="List of positive factors that influenced selection"
    )
    rejected_strategies: Dict[str, str] = Field(
        default_factory=dict,
        description="Map of rejected candidate strategies to their rejection rationale"
    )
    candidates: List[StrategyCandidate] = Field(
        default_factory=list,
        description="All evaluated candidate strategies for transparency"
    )
    fallback_strategy: Optional[AutomationStrategyType] = Field(
        default=None,
        description="Safe fallback strategy if primary strategy fails or becomes unavailable"
    )
    fallback_reason: Optional[str] = Field(
        default=None,
        description="Explanation of fallback selection"
    )
    is_mutating: bool = Field(default=False, description="Whether action mutates external or local state")
    requires_credentials: bool = Field(default=False, description="Whether execution requires credentials")
    credentials_available: bool = Field(default=True, description="Whether required credentials are present")


class AutomationPlan(BaseModel):
    """
    Phase 10: Explainable, deterministic automation plan for an entire workflow.
    Requires human approval prior to execution. Never executes autonomously.
    """
    plan_id: str = Field(default_factory=_generate_plan_id, description="Unique plan identifier")
    workflow_id: str = Field(..., description="Target workflow identifier")
    workflow_name: str = Field(..., description="Workflow display name")
    selected_strategy: AutomationStrategyType = Field(
        ...,
        description="Primary/predominant execution strategy for the workflow"
    )
    overall_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Aggregate heuristic suitability score across steps"
    )
    steps: List[StepPlan] = Field(..., description="Per-step automation decisions")
    requires_approval: bool = Field(
        default=True,
        description="Mandatory safety gate: human approval required before execution"
    )
    fallback_available: bool = Field(
        default=False,
        description="Whether safe fallback strategies are configured for automated steps"
    )
    explanation: Dict[str, Any] = Field(
        default_factory=dict,
        description="Overall explainability summary, key factors, and safety audit notes"
    )
    learning_state_summary: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Snapshot of Phase 9 learning state signals that influenced planning"
    )
    created_at: str = Field(
        default_factory=_current_iso_timestamp,
        description="ISO 8601 UTC creation timestamp"
    )


class AutomationPlanRequest(BaseModel):
    """
    Optional payload for POST /api/workflows/{workflow_id}/automation-plan.
    Allows specifying custom actions, proposal, or context parameters.
    """
    workflow_name: Optional[str] = Field(default=None, description="Optional custom workflow name")
    steps: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Optional list of action dictionaries to plan"
    )
    context: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Execution context, mock telemetry, or environment flags"
    )
    strategy_override: Optional[Dict[str, str]] = Field(
        default=None,
        description="Optional manual strategy preferences per step_id"
    )


class AutomationPlanResponse(BaseModel):
    """
    Standard API response containing the generated automation plan.
    """
    workflow_id: str
    plan: AutomationPlan
    requires_approval: bool = True
    message: str = (
        "Deterministic automation plan generated successfully. "
        "Human approval is mandatory before execution."
    )
