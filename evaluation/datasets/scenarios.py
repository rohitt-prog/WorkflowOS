"""
WorkFlowOS Phase 15: Benchmark Scenarios & Deterministic Ground Truth

Defines realistic operational activity scenarios (Scenarios A through J)
with explicit, deterministic ground truth specifications for evaluating
discovery, ranking, safety, planning, learning, and execution pipelines.

No random generators or LLMs are used to generate ground truth.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass(frozen=True)
class ExpectedWorkflow:
    """Explicit ground truth expectation for a single workflow pattern."""
    sequence: List[str]
    min_occurrences: int
    label: Optional[str] = None
    requires_approval: bool = False
    is_mutating: bool = False
    category: str = "general"


@dataclass(frozen=True)
class GroundTruth:
    """Explicit deterministic evaluation expectations for a scenario."""
    expected_detected: bool
    expected_workflows: List[ExpectedWorkflow] = field(default_factory=list)
    expected_occurrences: int = 0
    requires_approval: Optional[bool] = None
    is_executable: bool = True
    fail_closed: bool = False
    rejection_reason_contains: Optional[str] = None
    notes: str = ""


@dataclass
class BenchmarkScenario:
    """Complete evaluation scenario definition."""
    scenario_id: str
    code: str
    name: str
    description: str
    category: str
    session_sequences: Dict[str, List[str]]
    ground_truth: GroundTruth
    metadata: Dict[str, Any] = field(default_factory=dict)


def get_benchmark_scenarios() -> List[BenchmarkScenario]:
    """
    Constructs the canonical Phase 15 benchmark dataset covering Scenarios A through J.
    All data is deterministic and strictly synthetic.
    """
    canonical_support_sequence = [
        "open_email",
        "download_attachment",
        "search_customer",
        "update_customer",
        "send_message",
    ]

    scenarios: List[BenchmarkScenario] = [
        # Scenario A — Customer Support
        BenchmarkScenario(
            scenario_id="scenario_a_customer_support",
            code="SCENARIO_A",
            name="Customer Support Canonical Workflow",
            description="Canonical 5-step customer support workflow executed identically across 3 user sessions.",
            category="core_workflow",
            session_sequences={
                "session_a_1": list(canonical_support_sequence),
                "session_a_2": list(canonical_support_sequence),
                "session_a_3": list(canonical_support_sequence),
            },
            ground_truth=GroundTruth(
                expected_detected=True,
                expected_workflows=[
                    ExpectedWorkflow(
                        sequence=canonical_support_sequence,
                        min_occurrences=3,
                        label="Customer Request Processing",
                        requires_approval=True,
                        is_mutating=True,
                        category="support",
                    )
                ],
                expected_occurrences=3,
                requires_approval=True,
                is_executable=True,
                fail_closed=False,
                notes="Standard customer support workflow with update and message steps requiring approval.",
            ),
        ),

        # Scenario B — Repeated Workflow with Minor Variation
        BenchmarkScenario(
            scenario_id="scenario_b_repeated_minor_variation",
            code="SCENARIO_B",
            name="Repeated Workflow with Optional Step",
            description="Canonical 5-step workflow repeated 3 times, where one session omits download_attachment.",
            category="variation",
            session_sequences={
                "session_b_1": list(canonical_support_sequence),
                "session_b_2": [
                    "open_email",
                    "search_customer",
                    "update_customer",
                    "send_message",
                ],
                "session_b_3": list(canonical_support_sequence),
            },
            ground_truth=GroundTruth(
                expected_detected=True,
                expected_workflows=[
                    ExpectedWorkflow(
                        sequence=canonical_support_sequence,
                        min_occurrences=3,
                        label="Customer Request Processing",
                        requires_approval=True,
                        is_mutating=True,
                        category="support",
                    )
                ],
                expected_occurrences=3,
                requires_approval=True,
                is_executable=True,
                fail_closed=False,
                notes="Local alignment tolerates the omitted step and identifies canonical pattern with optional step.",
            ),
        ),

        # Scenario C — Similar but Different Workflows
        BenchmarkScenario(
            scenario_id="scenario_c_similar_distinct",
            code="SCENARIO_C",
            name="Similar Looking Distinct Workflows Maintained",
            description="Two workflows sharing a prefix and suffix but differing by critical operation (update vs cancel). Must not merge.",
            category="separation",
            session_sequences={
                "session_c_1": ["search_customer", "update_customer", "send_message"],
                "session_c_2": ["search_customer", "update_customer", "send_message"],
                "session_c_3": ["search_customer", "cancel_order", "send_message"],
                "session_c_4": ["search_customer", "cancel_order", "send_message"],
            },
            ground_truth=GroundTruth(
                expected_detected=True,
                expected_workflows=[
                    ExpectedWorkflow(
                        sequence=["search_customer", "update_customer", "send_message"],
                        min_occurrences=2,
                        label="Customer Account Tier Update",
                        requires_approval=True,
                        is_mutating=True,
                    ),
                    ExpectedWorkflow(
                        sequence=["search_customer", "cancel_order", "send_message"],
                        min_occurrences=2,
                        label="Order Cancellation Flow",
                        requires_approval=True,
                        is_mutating=True,
                    ),
                ],
                expected_occurrences=2,
                requires_approval=True,
                is_executable=True,
                fail_closed=False,
                notes="Two distinct business sequences must be preserved as separate workflows.",
            ),
        ),

        # Scenario D — Noise Insertion
        BenchmarkScenario(
            scenario_id="scenario_d_noise_insertion",
            code="SCENARIO_D",
            name="Workflow with Bounded Noise Insertion",
            description="Canonical workflow embedded with extraneous user navigation clicks (view_notifications, click_settings).",
            category="robustness",
            session_sequences={
                "session_d_1": [
                    "open_email",
                    "download_attachment",
                    "view_notifications",
                    "search_customer",
                    "update_customer",
                    "send_message",
                ],
                "session_d_2": list(canonical_support_sequence),
                "session_d_3": [
                    "open_email",
                    "download_attachment",
                    "search_customer",
                    "click_settings",
                    "update_customer",
                    "send_message",
                ],
            },
            ground_truth=GroundTruth(
                expected_detected=True,
                expected_workflows=[
                    ExpectedWorkflow(
                        sequence=canonical_support_sequence,
                        min_occurrences=3,
                        label="Customer Request Processing",
                        requires_approval=True,
                        is_mutating=True,
                    )
                ],
                expected_occurrences=3,
                requires_approval=True,
                is_executable=True,
                fail_closed=False,
                notes="Intermediate noise steps should be skipped by local sequence alignment.",
            ),
        ),

        # Scenario E — Short Sequence Below Threshold
        BenchmarkScenario(
            scenario_id="scenario_e_short_sequence",
            code="SCENARIO_E",
            name="Short Sequence Below Minimum Length Threshold",
            description="Repeated 2-step sequence below the minimum discovery threshold (min_length=3). Must reject.",
            category="threshold_negative",
            session_sequences={
                "session_e_1": ["open_email", "download_attachment"],
                "session_e_2": ["open_email", "download_attachment"],
                "session_e_3": ["open_email", "download_attachment"],
            },
            ground_truth=GroundTruth(
                expected_detected=False,
                expected_workflows=[],
                expected_occurrences=0,
                requires_approval=None,
                is_executable=False,
                fail_closed=False,
                notes="Must be rejected because length 2 is less than min_length=3 threshold.",
            ),
        ),

        # Scenario F — Single Occurrence
        BenchmarkScenario(
            scenario_id="scenario_f_single_occurrence",
            code="SCENARIO_F",
            name="Single Occurrence Below Frequency Threshold",
            description="Canonical 5-step workflow appearing only once across all user sessions. Must not be discovered.",
            category="frequency_negative",
            session_sequences={
                "session_f_1": list(canonical_support_sequence),
            },
            ground_truth=GroundTruth(
                expected_detected=False,
                expected_workflows=[],
                expected_occurrences=1,
                requires_approval=None,
                is_executable=False,
                fail_closed=False,
                notes="Must be rejected because occurrences 1 is less than min_occurrences=2 threshold.",
            ),
        ),

        # Scenario G — Multiple Sessions (Session Isolation)
        BenchmarkScenario(
            scenario_id="scenario_g_session_isolation",
            code="SCENARIO_G",
            name="Session Isolation Verification",
            description="Disjoint sub-sequences across separate sessions. Actions in session 1 must not bleed into session 2.",
            category="isolation",
            session_sequences={
                "session_g_1": ["open_email", "download_attachment"],
                "session_g_2": ["search_customer", "update_customer", "send_message"],
                "session_g_3": ["open_browser", "read_docs"],
            },
            ground_truth=GroundTruth(
                expected_detected=False,
                expected_workflows=[],
                expected_occurrences=0,
                requires_approval=None,
                is_executable=False,
                fail_closed=False,
                notes="No repeated workflow crosses session boundaries. Session isolation strictly maintained.",
            ),
        ),

        # Scenario H — Mutating Workflow (Approval Requirements)
        BenchmarkScenario(
            scenario_id="scenario_h_mutating_workflow",
            code="SCENARIO_H",
            name="Mutating Workflow Approval Enforcement",
            description="Workflow containing state-mutating actions (update_customer, send_message). Must enforce approval.",
            category="safety",
            session_sequences={
                "session_h_1": ["search_customer", "update_customer", "send_message"],
                "session_h_2": ["search_customer", "update_customer", "send_message"],
            },
            ground_truth=GroundTruth(
                expected_detected=True,
                expected_workflows=[
                    ExpectedWorkflow(
                        sequence=["search_customer", "update_customer", "send_message"],
                        min_occurrences=2,
                        requires_approval=True,
                        is_mutating=True,
                    )
                ],
                expected_occurrences=2,
                requires_approval=True,
                is_executable=True,
                fail_closed=False,
                notes="State mutation triggers mandatory human approval gate.",
            ),
        ),

        # Scenario I — Unknown Action (Fail-Closed Safety)
        BenchmarkScenario(
            scenario_id="scenario_i_unknown_action",
            code="SCENARIO_I",
            name="Unknown Action Fail-Closed Rejection",
            description="Workflow containing an unregistered action ('unknown_custom_action_xyz'). Must fail closed.",
            category="safety",
            session_sequences={
                "session_i_1": ["search_customer", "unknown_custom_action_xyz", "send_message"],
                "session_i_2": ["search_customer", "unknown_custom_action_xyz", "send_message"],
            },
            ground_truth=GroundTruth(
                expected_detected=True,  # Discovered as sequence pattern, but...
                expected_workflows=[
                    ExpectedWorkflow(
                        sequence=["search_customer", "unknown_custom_action_xyz", "send_message"],
                        min_occurrences=2,
                        requires_approval=True,
                        is_mutating=False,
                    )
                ],
                expected_occurrences=2,
                requires_approval=True,     # Must fail closed: require approval!
                is_executable=False,        # Execution MUST be rejected!
                fail_closed=True,
                rejection_reason_contains="not supported",
                notes="Unknown action cannot be marked read-only, must require approval, and must be rejected at execution.",
            ),
        ),

        # Scenario J — Unknown Application (Ecosystem Boundary)
        BenchmarkScenario(
            scenario_id="scenario_j_unknown_application",
            code="SCENARIO_J",
            name="Unknown Application Boundary Enforcement",
            description="Workflow targeting an unregistered application ('nonexistent_legacy_app'). Must reject execution.",
            category="safety",
            session_sequences={
                "session_j_1": ["open_doc", "edit_doc", "save_doc"],
                "session_j_2": ["open_doc", "edit_doc", "save_doc"],
            },
            ground_truth=GroundTruth(
                expected_detected=True,
                expected_workflows=[
                    ExpectedWorkflow(
                        sequence=["open_doc", "edit_doc", "save_doc"],
                        min_occurrences=2,
                        requires_approval=True,
                        is_mutating=False,
                    )
                ],
                expected_occurrences=2,
                requires_approval=True,
                is_executable=False,        # Unregistered app cannot execute!
                fail_closed=True,
                rejection_reason_contains="not registered",
                notes="Actions targeting an unknown application must be rejected fail-closed.",
            ),
        ),
    ]

    return scenarios


def get_scenario_by_id(scenario_id: str) -> Optional[BenchmarkScenario]:
    """Retrieves a single scenario by its unique identifier."""
    for s in get_benchmark_scenarios():
        if s.scenario_id == scenario_id or s.code == scenario_id:
            return s
    return None
