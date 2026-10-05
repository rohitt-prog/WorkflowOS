"""
WorkFlowOS Phase 8.1 & 8.2: Discovery Evaluation Framework & Synthetic Dataset

Defines:
1. Deterministic synthetic evaluation datasets covering Phase 8.1 and Phase 8.2 operational scenarios.
2. Ground-truth workflow definitions and expected detection outcomes.
3. Rigorous evaluation harness calculating Precision, Recall, F1, TP, FP, FN, and TN.
4. Comparative benchmark comparing Phase 8.1 baseline detector vs. Phase 8.2 local alignment detector.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple
import difflib

from discovery.detector import (
    RepetitionDetector,
    compute_sequence_similarity,
    get_deterministic_label,
)
from discovery.models import DiscoveryResult, DiscoveredWorkflow
from discovery.sequence import build_session_sequences


@dataclass
class GroundTruthWorkflow:
    """Expected workflow specification within an evaluation scenario."""
    sequence: List[str]
    min_occurrences: int
    label: Optional[str] = None


@dataclass
class EvaluationScenario:
    """A single deterministic test scenario with explicit ground truth."""
    scenario_id: str
    name: str
    description: str
    session_sequences: Dict[str, List[str]]
    expected_detected: bool
    expected_workflows: List[GroundTruthWorkflow] = field(default_factory=list)
    raw_events: Optional[List[Dict[str, Any]]] = None
    category: str = "general"


def build_synthetic_evaluation_dataset() -> List[EvaluationScenario]:
    """
    Constructs the 8 deterministic evaluation scenarios established in Phase 8.1.
    All data is completely synthetic with no PII.
    """
    scenarios: List[EvaluationScenario] = []

    canonical_5_step = [
        "open_email",
        "download_attachment",
        "search_customer",
        "update_customer",
        "send_message",
    ]

    # Scenario 1: Identical Repeated Workflows
    scenarios.append(
        EvaluationScenario(
            scenario_id="scenario_1_identical_repeated",
            name="Identical Repeated Workflows",
            description="Exact 5-step canonical sequence repeated across 4 separate user sessions.",
            session_sequences={
                "session_101": list(canonical_5_step),
                "session_102": list(canonical_5_step),
                "session_103": list(canonical_5_step),
                "session_104": list(canonical_5_step),
            },
            expected_detected=True,
            expected_workflows=[
                GroundTruthWorkflow(sequence=canonical_5_step, min_occurrences=4, label="Customer Request Processing")
            ],
            category="repeated_exact",
        )
    )

    # Scenario 2: Similar Sequences with Minor Variations
    scenarios.append(
        EvaluationScenario(
            scenario_id="scenario_2_minor_variations",
            name="Similar Sequences with Minor Variations",
            description="3 sessions where 1 session contains an extra inspect step (similarity ~0.83).",
            session_sequences={
                "session_201": [
                    "search_customer",
                    "update_customer",
                    "send_message",
                ],
                "session_202": [
                    "search_customer",
                    "view_customer_notes",
                    "update_customer",
                    "send_message",
                ],
                "session_203": [
                    "search_customer",
                    "update_customer",
                    "send_message",
                ],
            },
            expected_detected=True,
            expected_workflows=[
                GroundTruthWorkflow(
                    sequence=["search_customer", "update_customer", "send_message"],
                    min_occurrences=3,
                    label="Customer Account Tier Update",
                )
            ],
            category="variation",
        )
    )

    # Scenario 3: Unrelated Actions that Should NOT Form a Workflow
    scenarios.append(
        EvaluationScenario(
            scenario_id="scenario_3_unrelated_actions",
            name="Unrelated Actions (Noise Only)",
            description="Completely distinct random actions across sessions that should never form a workflow.",
            session_sequences={
                "session_301": ["open_settings", "export_log", "view_dashboard"],
                "session_302": ["delete_cache", "refresh_feed", "edit_profile"],
                "session_303": ["print_page", "scroll_down", "zoom_in"],
            },
            expected_detected=False,
            expected_workflows=[],
            category="negative_noise",
        )
    )

    # Scenario 4: Incomplete Sequences (Below min_length or truncated)
    scenarios.append(
        EvaluationScenario(
            scenario_id="scenario_4_incomplete_sequences",
            name="Incomplete / Truncated Sequences",
            description="Sessions with 1 or 2 actions only (below minimum workflow length threshold).",
            session_sequences={
                "session_401": ["open_email"],
                "session_402": ["open_email", "download_attachment"],
                "session_403": ["open_email"],
            },
            expected_detected=False,
            expected_workflows=[],
            category="negative_incomplete",
        )
    )

    # Scenario 5: Interleaved Activity from Separate Sessions
    interleaved_events = [
        {"session_id": "session_alpha", "timestamp": "2026-10-04T10:00:00Z", "event_type": "search_customer"},
        {"session_id": "session_beta", "timestamp": "2026-10-04T10:00:01Z", "event_type": "search_customer"},
        {"session_id": "session_alpha", "timestamp": "2026-10-04T10:00:02Z", "event_type": "update_customer"},
        {"session_id": "session_beta", "timestamp": "2026-10-04T10:00:03Z", "event_type": "update_customer"},
        {"session_id": "session_alpha", "timestamp": "2026-10-04T10:00:04Z", "event_type": "send_message"},
        {"session_id": "session_beta", "timestamp": "2026-10-04T10:00:05Z", "event_type": "send_message"},
    ]
    interleaved_session_seqs = build_session_sequences(interleaved_events)
    scenarios.append(
        EvaluationScenario(
            scenario_id="scenario_5_interleaved_sessions",
            name="Interleaved Multi-Session Activity",
            description="Events interleaved across sessions in chronological stream; must partition cleanly.",
            session_sequences=interleaved_session_seqs,
            raw_events=interleaved_events,
            expected_detected=True,
            expected_workflows=[
                GroundTruthWorkflow(
                    sequence=["search_customer", "update_customer", "send_message"],
                    min_occurrences=2,
                    label="Customer Account Tier Update",
                )
            ],
            category="interleaved",
        )
    )

    # Scenario 6: Frequent Common Actions (Monotonous Low-Entropy Noise)
    scenarios.append(
        EvaluationScenario(
            scenario_id="scenario_6_frequent_common_actions",
            name="Frequent Common Actions (Low-Entropy Repetition)",
            description="Monotonous repetitive action (view_dashboard repeated 3x); trivial action noise.",
            session_sequences={
                "session_601": ["view_dashboard", "view_dashboard", "view_dashboard"],
                "session_602": ["view_dashboard", "view_dashboard", "view_dashboard"],
                "session_603": ["view_dashboard", "view_dashboard", "view_dashboard"],
            },
            expected_detected=False,
            expected_workflows=[],
            category="negative_common_noise",
        )
    )

    # Scenario 7: Patterns with Occasional Missing or Reordered Actions
    scenarios.append(
        EvaluationScenario(
            scenario_id="scenario_7_missing_or_reordered",
            name="Patterns with Missing or Reordered Steps",
            description="Core 5-step flow with 1 session missing an action and 1 session with swapped adjacent steps.",
            session_sequences={
                "session_701": [
                    "open_email",
                    "download_attachment",
                    "search_customer",
                    "update_customer",
                    "send_message",
                ],
                "session_702": [
                    "open_email",
                    "search_customer",
                    "update_customer",
                    "send_message",
                ],
                "session_703": [
                    "open_email",
                    "download_attachment",
                    "update_customer",
                    "search_customer",
                    "send_message",
                ],
            },
            expected_detected=True,
            expected_workflows=[
                GroundTruthWorkflow(sequence=canonical_5_step, min_occurrences=2, label="Customer Request Processing")
            ],
            category="variation_reordered",
        )
    )

    # Scenario 8: Similar but Distinct Workflows (Must NOT be Merged)
    workflow_billing = [
        "open_email",
        "download_attachment",
        "record_payment",
        "send_receipt",
        "archive_thread",
    ]
    workflow_support = [
        "open_email",
        "download_attachment",
        "create_ticket",
        "assign_agent",
        "send_acknowledgement",
    ]
    scenarios.append(
        EvaluationScenario(
            scenario_id="scenario_8_distinct_workflows_no_merge",
            name="Similar but Distinct Workflows (No Incorrect Merge)",
            description="Two separate workflows sharing prefix steps; must be discovered as two distinct patterns.",
            session_sequences={
                "session_801": list(workflow_billing),
                "session_802": list(workflow_billing),
                "session_803": list(workflow_support),
                "session_804": list(workflow_support),
            },
            expected_detected=True,
            expected_workflows=[
                GroundTruthWorkflow(sequence=workflow_billing, min_occurrences=2, label="Billing & Payment Processing"),
                GroundTruthWorkflow(sequence=workflow_support, min_occurrences=2, label="Support Ticket Routine"),
            ],
            category="distinct_multi_pattern",
        )
    )

    return scenarios


def build_phase8_2_evaluation_dataset() -> List[EvaluationScenario]:
    """
    Constructs the 8 additional deterministic evaluation scenarios introduced in Phase 8.2.
    Tests local alignment, embedded subsequences, noise tolerance, single-session isolation,
    and excessive variation rejection.
    """
    scenarios: List[EvaluationScenario] = []

    canonical_5_step = [
        "open_email",
        "download_attachment",
        "search_customer",
        "update_customer",
        "send_message",
    ]

    # Scenario 9: Repeated Workflow Embedded Within Longer Noisy Sessions
    scenarios.append(
        EvaluationScenario(
            scenario_id="scenario_9_embedded_subsequence_with_noise",
            name="Repeated Subsequence Embedded in Longer Sessions",
            description="Canonical 5-step workflow surrounded by arbitrary login/logout and navigation actions.",
            session_sequences={
                "session_901": ["login", "view_home"] + list(canonical_5_step) + ["logout"],
                "session_902": ["refresh_feed", "open_browser"] + list(canonical_5_step),
                "session_903": list(canonical_5_step) + ["close_tab", "archive_session"],
            },
            expected_detected=True,
            expected_workflows=[
                GroundTruthWorkflow(sequence=canonical_5_step, min_occurrences=3, label="Customer Request Processing")
            ],
            category="embedded_subsequence",
        )
    )

    # Scenario 10: Extra Actions Inserted Between Workflow Steps
    scenarios.append(
        EvaluationScenario(
            scenario_id="scenario_10_interleaved_inserted_actions",
            name="Extra Actions Inserted Between Workflow Steps",
            description="Intermediate non-workflow actions (view_dashboard, view_profile) inserted between steps.",
            session_sequences={
                "session_1001": list(canonical_5_step),
                "session_1002": [
                    "open_email",
                    "view_dashboard",
                    "download_attachment",
                    "search_customer",
                    "update_customer",
                    "send_message",
                ],
                "session_1003": [
                    "open_email",
                    "download_attachment",
                    "search_customer",
                    "view_profile",
                    "update_customer",
                    "send_message",
                ],
            },
            expected_detected=True,
            expected_workflows=[
                GroundTruthWorkflow(sequence=canonical_5_step, min_occurrences=3, label="Customer Request Processing")
            ],
            category="inserted_actions",
        )
    )

    # Scenario 11: Single-Session Repetition (Must NOT Count as Repeated Multi-Session Workflow)
    # 3 repetitions within 1 session, but 0 other sessions support it.
    scenarios.append(
        EvaluationScenario(
            scenario_id="scenario_11_single_session_repetition_rejected",
            name="Single-Session Repetition Rejected (< min_occurrences)",
            description="Pattern repeated 3 times within a single session, but unsupported by any other session.",
            session_sequences={
                "session_1101": [
                    "search_customer", "update_customer", "send_message",
                    "search_customer", "update_customer", "send_message",
                    "search_customer", "update_customer", "send_message",
                ],
                "session_1102": ["edit_profile", "change_theme", "export_data"],
            },
            expected_detected=False,
            expected_workflows=[],
            category="single_session_repetition",
        )
    )

    # Scenario 12: Adjacent Step Transpositions (Reordered Steps)
    scenarios.append(
        EvaluationScenario(
            scenario_id="scenario_12_adjacent_step_transpositions",
            name="Small Adjacent Step Transposition Tolerated",
            description="Adjacent CRM steps (search vs update) swapped in 1 session; tolerated via Damerau alignment.",
            session_sequences={
                "session_1201": list(canonical_5_step),
                "session_1202": [
                    "open_email",
                    "download_attachment",
                    "update_customer",
                    "search_customer",
                    "send_message",
                ],
                "session_1203": list(canonical_5_step),
            },
            expected_detected=True,
            expected_workflows=[
                GroundTruthWorkflow(sequence=canonical_5_step, min_occurrences=3, label="Customer Request Processing")
            ],
            category="transposition",
        )
    )

    # Scenario 13: Shared Prefix Distinct Workflows (Billing vs Support)
    workflow_billing = [
        "open_email",
        "download_attachment",
        "record_payment",
        "send_receipt",
        "archive_thread",
    ]
    workflow_support = [
        "open_email",
        "download_attachment",
        "create_ticket",
        "assign_agent",
        "send_acknowledgement",
    ]
    scenarios.append(
        EvaluationScenario(
            scenario_id="scenario_13_shared_prefix_distinct_workflows",
            name="Shared Prefix Workflows Kept Separate",
            description="Two separate business workflows sharing a 2-step prefix; must never be merged.",
            session_sequences={
                "session_1301": list(workflow_billing),
                "session_1302": list(workflow_billing),
                "session_1303": list(workflow_support),
                "session_1304": list(workflow_support),
            },
            expected_detected=True,
            expected_workflows=[
                GroundTruthWorkflow(sequence=workflow_billing, min_occurrences=2, label="Billing & Payment Processing"),
                GroundTruthWorkflow(sequence=workflow_support, min_occurrences=2, label="Support Ticket Routine"),
            ],
            category="shared_prefix",
        )
    )

    # Scenario 14: Excessive Variation Rejected (Negative Test)
    scenarios.append(
        EvaluationScenario(
            scenario_id="scenario_14_excessive_variation_rejected",
            name="Excessive Sequence Variation Rejected",
            description="Sessions sharing only 1 or 2 scattered steps out of 5 (>60% edit distance); must reject.",
            session_sequences={
                "session_1401": list(canonical_5_step),
                "session_1402": ["open_email", "browse_catalog", "add_to_cart", "checkout", "send_message"],
                "session_1403": ["open_email", "view_faq", "submit_feedback", "rate_app", "send_message"],
            },
            expected_detected=False,
            expected_workflows=[],
            category="excessive_variation",
        )
    )

    # Scenario 15: Mixture of Exact and Locally Aligned Matches
    scenarios.append(
        EvaluationScenario(
            scenario_id="scenario_15_mixture_exact_and_local",
            name="Mixture of Exact and Locally Aligned Matches",
            description="4 sessions: 2 exact canonical, 1 embedded with outer noise, 1 with intermediate inserted step.",
            session_sequences={
                "session_1501": list(canonical_5_step),
                "session_1502": list(canonical_5_step),
                "session_1503": ["init_client", "open_email", "download_attachment", "search_customer", "update_customer", "send_message", "cleanup"],
                "session_1504": ["open_email", "check_status", "download_attachment", "search_customer", "update_customer", "send_message"],
            },
            expected_detected=True,
            expected_workflows=[
                GroundTruthWorkflow(sequence=canonical_5_step, min_occurrences=4, label="Customer Request Processing")
            ],
            category="mixture_alignment",
        )
    )

    # Scenario 16: Similar Looking Distinct Workflows (Must NOT be Merged)
    wf_crm_update = ["search_customer", "update_customer", "send_message", "log_audit"]
    wf_crm_delete = ["search_customer", "delete_customer", "send_message", "log_audit"]
    scenarios.append(
        EvaluationScenario(
            scenario_id="scenario_16_similar_looking_distinct_workflows",
            name="Similar Looking Distinct Workflows Maintained",
            description="Two workflows differing by a critical operational verb (update vs delete); must not merge.",
            session_sequences={
                "session_1601": list(wf_crm_update),
                "session_1602": list(wf_crm_update),
                "session_1603": list(wf_crm_delete),
                "session_1604": list(wf_crm_delete),
            },
            expected_detected=True,
            expected_workflows=[
                GroundTruthWorkflow(sequence=wf_crm_update, min_occurrences=2, label="Customer Update Flow"),
                GroundTruthWorkflow(sequence=wf_crm_delete, min_occurrences=2, label="Customer Delete Flow"),
            ],
            category="similar_distinct",
        )
    )

    return scenarios


def build_phase8_3_evaluation_dataset() -> List[EvaluationScenario]:
    """
    Constructs the 8 deterministic evaluation scenarios established in Phase 8.3:
    Scenario 17: Exact duplicates across multiple extraction paths collapsed to 1 representative.
    Scenario 18: Overlapping shadow patterns (shorter sub-slices with identical session support suppressed).
    Scenario 19: Short valid workflows preserved (3-step workflows preserved, not suppressed by noise filters).
    Scenario 20: Frequent common-action noise (monotonous repetitions suppressed by noise filtering).
    Scenario 21: Genuinely distinct business workflows maintained (not falsely merged).
    Scenario 22: Variable session support ranking (high-volume workflow ranked higher than low-volume).
    Scenario 23: Legitimate repeated actions in valid workflow (workflow with repeated comments preserved).
    Scenario 24: Weak marginal pattern with low ranking / noise rejected.
    """
    scenarios: List[EvaluationScenario] = []

    canonical_5_step = [
        "open_email",
        "download_attachment",
        "search_customer",
        "update_customer",
        "send_message",
    ]

    # Scenario 17: Exact Duplicate Sequences
    scenarios.append(
        EvaluationScenario(
            scenario_id="scenario_17_exact_duplicates",
            name="Exact Duplicate Sequences Collapsed",
            description="Identical 5-step sequence occurring in multiple sessions; candidate deduplication must retain only 1 representative.",
            session_sequences={
                "session_1701": list(canonical_5_step),
                "session_1702": list(canonical_5_step),
                "session_1703": list(canonical_5_step),
            },
            expected_detected=True,
            expected_workflows=[
                GroundTruthWorkflow(sequence=canonical_5_step, min_occurrences=3, label="Customer Request Processing")
            ],
            category="exact_duplicate",
        )
    )

    # Scenario 18: Overlapping Shadow Subsequences
    scenarios.append(
        EvaluationScenario(
            scenario_id="scenario_18_overlapping_shadow_subsequence",
            name="Overlapping Shadow Subsequences Suppressed",
            description="3-step sub-slice appearing only in sessions that contain the 5-step workflow; shorter shadow must be suppressed.",
            session_sequences={
                "session_1801": list(canonical_5_step),
                "session_1802": list(canonical_5_step),
                "session_1803": list(canonical_5_step),
            },
            expected_detected=True,
            expected_workflows=[
                GroundTruthWorkflow(sequence=canonical_5_step, min_occurrences=3, label="Customer Request Processing")
            ],
            category="overlapping_shadow",
        )
    )

    # Scenario 19: Short Valid Workflow Preserved
    short_crm_update = ["search_customer", "update_customer", "send_message"]
    scenarios.append(
        EvaluationScenario(
            scenario_id="scenario_19_short_valid_workflow",
            name="Short Valid Workflow Preserved",
            description="3-step customer tier update routine; must not be discarded by noise filtering.",
            session_sequences={
                "session_1901": list(short_crm_update),
                "session_1902": list(short_crm_update),
                "session_1903": list(short_crm_update),
            },
            expected_detected=True,
            expected_workflows=[
                GroundTruthWorkflow(sequence=short_crm_update, min_occurrences=3, label="Customer Account Tier Update")
            ],
            category="short_valid",
        )
    )

    # Scenario 20: Frequent Common-Action Noise Suppressed
    scenarios.append(
        EvaluationScenario(
            scenario_id="scenario_20_frequent_common_action_noise",
            name="Monotonous Loop Repetition Suppressed",
            description="Monotonous loop repeating view_dashboard x 3 across sessions; must be suppressed by noise filtering.",
            session_sequences={
                "session_2001": ["view_dashboard", "view_dashboard", "view_dashboard"],
                "session_2002": ["view_dashboard", "view_dashboard", "view_dashboard"],
                "session_2003": ["view_dashboard", "view_dashboard", "view_dashboard"],
            },
            expected_detected=False,
            expected_workflows=[],
            category="noise_reduction",
        )
    )

    # Scenario 21: Genuinely Distinct Workflows Maintained
    wf_order_fulfill = ["create_order", "process_payment", "pack_items", "dispatch_delivery"]
    wf_order_cancel = ["create_order", "cancel_order", "refund_payment", "restock_items"]
    scenarios.append(
        EvaluationScenario(
            scenario_id="scenario_21_distinct_business_workflows",
            name="Genuinely Distinct Workflows Maintained",
            description="Two separate e-commerce workflows sharing initial action; must not merge or suppress each other.",
            session_sequences={
                "session_2101": list(wf_order_fulfill),
                "session_2102": list(wf_order_fulfill),
                "session_2103": list(wf_order_cancel),
                "session_2104": list(wf_order_cancel),
            },
            expected_detected=True,
            expected_workflows=[
                GroundTruthWorkflow(sequence=wf_order_fulfill, min_occurrences=2, label="Order Fulfillment Routine"),
                GroundTruthWorkflow(sequence=wf_order_cancel, min_occurrences=2, label="Order Cancellation Routine"),
            ],
            category="distinct_workflows",
        )
    )

    # Scenario 22: Variable Session Support Ranking
    wf_high_volume = ["search_customer", "update_customer", "send_message"]
    wf_low_volume = ["open_document", "edit_document", "export_document"]
    scenarios.append(
        EvaluationScenario(
            scenario_id="scenario_22_variable_support_ranking",
            name="Variable Session Support Ranking",
            description="High-volume CRM workflow (6 sessions) vs low-volume doc workflow (2 sessions); CRM workflow must rank higher.",
            session_sequences={
                "session_2201": list(wf_high_volume),
                "session_2202": list(wf_high_volume),
                "session_2203": list(wf_high_volume),
                "session_2204": list(wf_high_volume),
                "session_2205": list(wf_high_volume),
                "session_2206": list(wf_high_volume),
                "session_2207": list(wf_low_volume),
                "session_2208": list(wf_low_volume),
            },
            expected_detected=True,
            expected_workflows=[
                GroundTruthWorkflow(sequence=wf_high_volume, min_occurrences=6, label="Customer Account Tier Update"),
                GroundTruthWorkflow(sequence=wf_low_volume, min_occurrences=2, label="Document Editing Routine"),
            ],
            category="support_ranking",
        )
    )

    # Scenario 23: Legitimate Repeated Actions in Valid Workflow
    wf_doc_review = ["open_document", "add_review_comment", "add_review_comment", "submit_approval"]
    scenarios.append(
        EvaluationScenario(
            scenario_id="scenario_23_legitimate_repeated_actions",
            name="Legitimate Repeated Actions in Valid Workflow",
            description="Document review routine containing intentional repeated comments; must not be falsely rejected as noise.",
            session_sequences={
                "session_2301": list(wf_doc_review),
                "session_2302": list(wf_doc_review),
                "session_2303": list(wf_doc_review),
            },
            expected_detected=True,
            expected_workflows=[
                GroundTruthWorkflow(sequence=wf_doc_review, min_occurrences=3, label="Document Review & Approval Routine")
            ],
            category="legitimate_repeated_actions",
        )
    )

    # Scenario 24: Weak Marginal Pattern with Low Ranking
    scenarios.append(
        EvaluationScenario(
            scenario_id="scenario_24_weak_marginal_pattern",
            name="Weak Marginal Pattern Rejected",
            description="Inconsistent sessions with low similarity and no coherent repeated structure; must be rejected.",
            session_sequences={
                "session_2401": ["open_email", "random_act_1", "random_act_2"],
                "session_2402": ["view_dashboard", "random_act_3", "random_act_4"],
                "session_2403": ["open_settings", "random_act_5", "random_act_6"],
            },
            expected_detected=False,
            expected_workflows=[],
            category="marginal_rejection",
        )
    )

    return scenarios


def build_phase8_5_evaluation_dataset() -> List[EvaluationScenario]:
    """
    Constructs the 9 deterministic evaluation scenarios introduced in Phase 8.5:
    Category A (Scenario 25): Workflow with Optional Step Omission (download_attachment omitted in 1 session).
    Category B (Scenario 26): Workflow with Intermediate Bounded Noise (tolerated non-workflow noise clicks).
    Category C (Scenario 27): Workflow with Partial Support Tracking (partial execution session tracked).
    Category D (Scenario 28): Variable Workflow Positions Across Sessions (start, middle, and end positions).
    Category E (Scenario 29): Intra-Session Repetitions (multiple executions in a single session recorded).
    Category F (Scenario 30): Generic Alternating Navigation Loop Suppressed (ping-pong noise rejected).
    Category G (Scenario 31): Independent Subsequences Preserved (shorter workflow with independent sessions not suppressed).
    Category H (Scenario 32): Similar Verbs on Distinct Entities Kept Separate (Customer Profile vs Product Catalog).
    Category I (Scenario 33): Multiple Valid Workflows in Same Session (Order Fulfillment + Document Editing).
    """
    scenarios: List[EvaluationScenario] = []

    canonical_5_step = [
        "open_email",
        "download_attachment",
        "search_customer",
        "update_customer",
        "send_message",
    ]

    # Scenario 25: Category A - Optional Step Omission
    scenarios.append(
        EvaluationScenario(
            scenario_id="scenario_25_optional_step_omission",
            name="Workflow with Optional Step Omission",
            description="5-step workflow where 1 session omits download_attachment; flow qualifies with optional_steps detected.",
            session_sequences={
                "session_2501": list(canonical_5_step),
                "session_2502": ["open_email", "search_customer", "update_customer", "send_message"],
                "session_2503": list(canonical_5_step),
            },
            expected_detected=True,
            expected_workflows=[
                GroundTruthWorkflow(sequence=canonical_5_step, min_occurrences=3, label="Customer Request Processing")
            ],
            category="optional_step",
        )
    )

    # Scenario 26: Category B - Intermediate Bounded Noise
    scenarios.append(
        EvaluationScenario(
            scenario_id="scenario_26_intermediate_bounded_noise",
            name="Workflow with Bounded Intermediate Noise",
            description="Sessions contain 1-2 extraneous navigation clicks between workflow steps; bounded noise tolerance preserves workflow.",
            session_sequences={
                "session_2601": ["open_email", "download_attachment", "view_notifications", "search_customer", "update_customer", "send_message"],
                "session_2602": list(canonical_5_step),
                "session_2603": ["open_email", "download_attachment", "search_customer", "click_settings", "update_customer", "send_message"],
            },
            expected_detected=True,
            expected_workflows=[
                GroundTruthWorkflow(sequence=canonical_5_step, min_occurrences=3, label="Customer Request Processing")
            ],
            category="intermediate_noise",
        )
    )

    # Scenario 27: Category C - Partial Execution Tracking
    scenarios.append(
        EvaluationScenario(
            scenario_id="scenario_27_partial_execution_tracking",
            name="Workflow with Partial Support Tracking",
            description="2 full sessions and 1 session with partial execution (3/5 steps); flow qualifies on 2 full sessions, partial support tracked separately.",
            session_sequences={
                "session_2701": list(canonical_5_step),
                "session_2702": list(canonical_5_step),
                "session_2703": ["open_email", "download_attachment", "search_customer"],
            },
            expected_detected=True,
            expected_workflows=[
                GroundTruthWorkflow(sequence=canonical_5_step, min_occurrences=2, label="Customer Request Processing")
            ],
            category="partial_execution",
        )
    )

    # Scenario 28: Category D - Variable Workflow Positions Across Sessions
    scenarios.append(
        EvaluationScenario(
            scenario_id="scenario_28_variable_workflow_positions",
            name="Position-Independent Workflow Matching",
            description="Canonical 5-step workflow occurs at start of session 1, middle of session 2, and end of session 3.",
            session_sequences={
                "session_2801": list(canonical_5_step) + ["cleanup_desk", "logout"],
                "session_2802": ["init_system", "check_calendar"] + list(canonical_5_step) + ["save_session"],
                "session_2803": ["login", "read_slack"] + list(canonical_5_step),
            },
            expected_detected=True,
            expected_workflows=[
                GroundTruthWorkflow(sequence=canonical_5_step, min_occurrences=3, label="Customer Request Processing")
            ],
            category="variable_positions",
        )
    )

    # Scenario 29: Category E - Intra-Session Repetition Tracking
    wf_doc_edit = ["open_document", "edit_document", "export_document"]
    scenarios.append(
        EvaluationScenario(
            scenario_id="scenario_29_intra_session_repetition",
            name="Intra-Session Repetition Tracking",
            description="Document editing routine executed twice in session 1 and once in session 2; qualifies across 2 sessions, with 1 intra-session repetition recorded.",
            session_sequences={
                "session_2901": ["open_document", "edit_document", "export_document", "check_inbox", "open_document", "edit_document", "export_document"],
                "session_2902": list(wf_doc_edit),
            },
            expected_detected=True,
            expected_workflows=[
                GroundTruthWorkflow(sequence=wf_doc_edit, min_occurrences=2, label="Document Editing Routine")
            ],
            category="intra_session_repetition",
        )
    )

    # Scenario 30: Category F - Generic Alternating Navigation Loop Suppressed
    scenarios.append(
        EvaluationScenario(
            scenario_id="scenario_30_generic_alternating_navigation_loop",
            name="Generic Alternating Navigation Loop Suppressed",
            description="Alternating ping-pong navigation loop (open_tab, search_tab x 3) suppressed by noise reduction.",
            session_sequences={
                "session_3001": ["open_tab", "search_tab", "open_tab", "search_tab", "open_tab", "search_tab"],
                "session_3002": ["open_tab", "search_tab", "open_tab", "search_tab", "open_tab", "search_tab"],
                "session_3003": ["open_tab", "search_tab", "open_tab", "search_tab", "open_tab", "search_tab"],
            },
            expected_detected=False,
            expected_workflows=[],
            category="generic_repeated_noise",
        )
    )

    # Scenario 31: Category G - Independent Subsequences Preserved
    crm_short_3 = ["search_customer", "update_customer", "send_message"]
    scenarios.append(
        EvaluationScenario(
            scenario_id="scenario_31_independent_subsequences_preserved",
            name="Independent Subsequences Preserved",
            description="Shorter 3-step routine occurs inside 5-step flow in sessions 1-2, but independently in sessions 3-4; both preserved.",
            session_sequences={
                "session_3101": list(canonical_5_step),
                "session_3102": list(canonical_5_step),
                "session_3103": list(crm_short_3),
                "session_3104": list(crm_short_3),
            },
            expected_detected=True,
            expected_workflows=[
                GroundTruthWorkflow(sequence=canonical_5_step, min_occurrences=2, label="Customer Request Processing"),
                GroundTruthWorkflow(sequence=crm_short_3, min_occurrences=4, label="Customer Account Tier Update"),
            ],
            category="independent_subsequences",
        )
    )

    # Scenario 32: Category H - Similar Verbs on Distinct Entities Kept Separate
    wf_customer_profile = ["search_customer", "open_customer", "update_customer"]
    wf_product_catalog = ["search_product", "open_product", "update_product"]
    scenarios.append(
        EvaluationScenario(
            scenario_id="scenario_32_distinct_entity_sequences",
            name="Similar Verbs on Distinct Entities Kept Separate",
            description="Customer Profile Management vs Product Catalog Update; both maintained distinctly without merging.",
            session_sequences={
                "session_3201": list(wf_customer_profile),
                "session_3202": list(wf_customer_profile),
                "session_3203": list(wf_product_catalog),
                "session_3204": list(wf_product_catalog),
            },
            expected_detected=True,
            expected_workflows=[
                GroundTruthWorkflow(sequence=wf_customer_profile, min_occurrences=2, label="Customer Profile Management"),
                GroundTruthWorkflow(sequence=wf_product_catalog, min_occurrences=2, label="Product Catalog Update"),
            ],
            category="distinct_entities",
        )
    )

    # Scenario 33: Category I - Multiple Valid Workflows in Same Session
    wf_order_fulfill = ["create_order", "process_payment", "pack_items", "dispatch_delivery"]
    scenarios.append(
        EvaluationScenario(
            scenario_id="scenario_33_multiple_valid_workflows_same_session",
            name="Multiple Valid Workflows in Same Sessions",
            description="Order Fulfillment Routine and Document Editing Routine both executed within the same sessions.",
            session_sequences={
                "session_3301": list(wf_order_fulfill) + ["browse_catalog", "check_metrics", "read_slack", "export_log"] + list(wf_doc_edit),
                "session_3302": list(wf_order_fulfill) + ["manage_settings", "zoom_meeting", "take_notes", "save_preferences"] + list(wf_doc_edit),
            },
            expected_detected=True,
            expected_workflows=[
                GroundTruthWorkflow(sequence=wf_order_fulfill, min_occurrences=2, label="Order Fulfillment Routine"),
                GroundTruthWorkflow(sequence=wf_doc_edit, min_occurrences=2, label="Document Editing Routine"),
            ],
            category="multiple_workflows_same_session",
        )
    )

    return scenarios


def build_full_evaluation_dataset() -> List[EvaluationScenario]:
    """
    Combines Phase 8.1 regression scenarios (1-8) and Phase 8.2 scenarios (9-16).
    Total 16 deterministic scenarios.
    """
    return build_synthetic_evaluation_dataset() + build_phase8_2_evaluation_dataset()


def build_complete_benchmark_dataset() -> List[EvaluationScenario]:
    """
    Combines Phase 8.1 regression (1-8), Phase 8.2 (9-16), and Phase 8.3 (17-24).
    Total 24 deterministic evaluation scenarios.
    Maintained for backward compatibility with Phase 8.3 / Phase 8.4 tests.
    """
    return (
        build_synthetic_evaluation_dataset()
        + build_phase8_2_evaluation_dataset()
        + build_phase8_3_evaluation_dataset()
    )


def build_phase8_5_benchmark_dataset() -> List[EvaluationScenario]:
    """
    Combines Phase 8.1 (1-8), Phase 8.2 (9-16), Phase 8.3 (17-24), and Phase 8.5 (25-33).
    Total 33 deterministic evaluation scenarios.
    """
    return (
        build_synthetic_evaluation_dataset()
        + build_phase8_2_evaluation_dataset()
        + build_phase8_3_evaluation_dataset()
        + build_phase8_5_evaluation_dataset()
    )


class LegacyPhase81Detector:
    """
    Baseline Phase 8.1 detector implementation (global SequenceMatcher without local alignment)
    used for empirical before-and-after comparison.
    """

    def __init__(self, min_length: int = 3, min_occurrences: int = 2, similarity_threshold: float = 0.8):
        self.min_length = min_length
        self.min_occurrences = min_occurrences
        self.similarity_threshold = similarity_threshold

    def detect(self, session_sequences: Dict[str, List[str]], **kwargs) -> DiscoveryResult:
        qualified_sessions = {
            sid: seq for sid, seq in session_sequences.items() if len(seq) >= self.min_length
        }
        if len(qualified_sessions) < self.min_occurrences:
            return DiscoveryResult(detected=False, workflows=[], suppressed_workflows=[], total_candidates_evaluated=0)

        exact_clusters: Dict[Tuple[str, ...], List[str]] = {}
        for sid, seq in qualified_sessions.items():
            exact_clusters.setdefault(tuple(seq), []).append(sid)

        sorted_patterns = sorted(
            exact_clusters.keys(),
            key=lambda p: (len(exact_clusters[p]), len(p)),
            reverse=True,
        )

        discovered_workflows: List[DiscoveredWorkflow] = []
        assigned_sessions = set()

        for pattern in sorted_patterns:
            canonical_seq = list(pattern)
            matched_sessions: List[Tuple[str, float]] = []

            for sid in exact_clusters[pattern]:
                if sid not in assigned_sessions:
                    matched_sessions.append((sid, 1.0))

            for sid, seq in qualified_sessions.items():
                if sid in assigned_sessions or any(sid == m[0] for m in matched_sessions):
                    continue
                # Global SequenceMatcher ratio
                matcher = difflib.SequenceMatcher(None, canonical_seq, seq)
                sim = round(matcher.ratio(), 4)
                if sim >= self.similarity_threshold:
                    matched_sessions.append((sid, sim))

            if len(matched_sessions) >= self.min_occurrences:
                for sid, _ in matched_sessions:
                    assigned_sessions.add(sid)

                avg_similarity = round(
                    sum(sim for _, sim in matched_sessions) / len(matched_sessions), 4
                )
                discovered_workflows.append(
                    DiscoveredWorkflow(
                        label=get_deterministic_label(canonical_seq),
                        sequence=canonical_seq,
                        occurrences=len(matched_sessions),
                        similarity=avg_similarity,
                        session_ids=[sid for sid, _ in matched_sessions],
                    )
                )

        return DiscoveryResult(
            detected=len(discovered_workflows) > 0,
            workflows=discovered_workflows,
            suppressed_workflows=[],
            total_candidates_evaluated=len(sorted_patterns),
        )


@dataclass
class EvaluationReport:
    """Comprehensive evaluation metrics report."""
    total_scenarios: int
    true_positives: int
    false_positives: int
    false_negatives: int
    true_negatives: int
    precision: float
    recall: float
    f1_score: float
    accuracy: float
    duplicate_suppressions: int = 0
    total_candidates_evaluated: int = 0
    # Phase 8.5 robustness metrics:
    exact_replay_count: int = 0
    approximate_replay_count: int = 0
    partial_support_count: int = 0
    optional_step_count: int = 0
    intra_session_repetition_count: int = 0
    average_alignment_similarity: float = 0.0
    candidates_before_filtering: int = 0
    candidates_after_filtering: int = 0
    scenario_details: List[Dict[str, Any]] = field(default_factory=list)


def evaluate_discovery_engine(
    detector: Optional[Any] = None,
    dataset: Optional[List[EvaluationScenario]] = None,
    similarity_match_threshold: float = 0.8,
) -> EvaluationReport:
    """
    Evaluates a Discovery Engine against an evaluation dataset.

    Definition of Evaluation Metrics:
    - True Positive (TP): An expected ground-truth workflow is detected by the engine with
      sequence similarity >= similarity_match_threshold to the ground-truth sequence.
    - False Positive (FP):
      a) The engine detected a workflow in a negative scenario where NO workflow was expected.
      b) The engine detected an extra spurious workflow that does not match any expected workflow.
      c) Two distinct workflows were improperly merged into a single pattern.
    - False Negative (FN): An expected ground-truth workflow was NOT detected by the engine.
    - True Negative (TN): A negative scenario where no workflow was expected, and the engine
      correctly reported detected=False with 0 workflows.
    """
    active_detector = detector or RepetitionDetector(min_length=3, min_occurrences=2, similarity_threshold=0.8)
    scenarios = dataset or build_synthetic_evaluation_dataset()

    tp = 0
    fp = 0
    fn = 0
    tn = 0
    total_dup_suppressions = 0
    total_candidates = 0
    total_exact_replays = 0
    total_approx_replays = 0
    total_partial_support = 0
    total_optional_steps = 0
    total_intra_reps = 0
    total_sim_sum = 0.0
    total_sim_count = 0
    total_candidates_before = 0
    total_candidates_after = 0
    scenario_details: List[Dict[str, Any]] = []

    for scenario in scenarios:
        if hasattr(active_detector, "detect"):
            try:
                result = active_detector.detect(scenario.session_sequences, include_suppressed=True)
            except TypeError:
                result = active_detector.detect(scenario.session_sequences)
        else:
            result = active_detector.detect(scenario.session_sequences)

        detected_workflows = result.workflows
        if hasattr(result, "suppressed_workflows") and result.suppressed_workflows:
            total_dup_suppressions += len(result.suppressed_workflows)
        if hasattr(result, "total_candidates_evaluated"):
            total_candidates += result.total_candidates_evaluated
            total_candidates_before += result.total_candidates_evaluated

        total_candidates_after += len(detected_workflows)

        for det_wf in detected_workflows:
            total_sim_sum += det_wf.similarity
            total_sim_count += 1
            total_partial_support += getattr(det_wf, "partial_support_count", 0)
            total_optional_steps += len(getattr(det_wf, "optional_steps", []))
            total_intra_reps += getattr(det_wf, "intra_session_repetitions", 0)

            if det_wf.explanation and hasattr(det_wf.explanation, "sequence_evidence") and det_wf.explanation.sequence_evidence:
                total_exact_replays += det_wf.explanation.sequence_evidence.exact_match_sessions_count
                total_approx_replays += det_wf.explanation.sequence_evidence.approximate_match_sessions_count
            elif det_wf.similarity >= 0.9999:
                total_exact_replays += det_wf.occurrences
            else:
                total_approx_replays += det_wf.occurrences

        scen_tp = 0
        scen_fp = 0
        scen_fn = 0
        scen_tn = 0

        if not scenario.expected_detected:
            # Negative scenario
            if len(detected_workflows) == 0:
                scen_tn += 1
                tn += 1
            else:
                # Detected workflows when none were expected -> False Positives
                scen_fp += len(detected_workflows)
                fp += len(detected_workflows)
        else:
            # Positive scenario: match detected against expected ground truth
            expected_remaining = list(scenario.expected_workflows)
            matched_detected_indices = set()

            for exp_wf in expected_remaining:
                found_match = False
                for d_idx, det_wf in enumerate(detected_workflows):
                    if d_idx in matched_detected_indices:
                        continue
                    sim = compute_sequence_similarity(exp_wf.sequence, det_wf.sequence)
                    if sim >= similarity_match_threshold:
                        found_match = True
                        matched_detected_indices.add(d_idx)
                        break

                if found_match:
                    scen_tp += 1
                    tp += 1
                else:
                    scen_fn += 1
                    fn += 1

            # Any detected workflow that did not match an expected ground truth is a False Positive
            unmatched_detected = len(detected_workflows) - len(matched_detected_indices)
            if unmatched_detected > 0:
                scen_fp += unmatched_detected
                fp += unmatched_detected

        scenario_details.append({
            "scenario_id": scenario.scenario_id,
            "name": scenario.name,
            "category": scenario.category,
            "expected_detected": scenario.expected_detected,
            "actual_detected": result.detected,
            "expected_count": len(scenario.expected_workflows),
            "actual_count": len(detected_workflows),
            "tp": scen_tp,
            "fp": scen_fp,
            "fn": scen_fn,
            "tn": scen_tn,
            "detected_sequences": [w.sequence for w in detected_workflows],
        })

    precision = round(tp / (tp + fp), 4) if (tp + fp) > 0 else 0.0
    recall = round(tp / (tp + fn), 4) if (tp + fn) > 0 else 0.0
    f1 = round(2 * precision * recall / (precision + recall), 4) if (precision + recall) > 0 else 0.0
    total_decisions = tp + fp + fn + tn
    accuracy = round((tp + tn) / total_decisions, 4) if total_decisions > 0 else 0.0
    avg_alignment = round(total_sim_sum / total_sim_count, 4) if total_sim_count > 0 else 0.0

    return EvaluationReport(
        total_scenarios=len(scenarios),
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
        true_negatives=tn,
        precision=precision,
        recall=recall,
        f1_score=f1,
        accuracy=accuracy,
        duplicate_suppressions=total_dup_suppressions,
        total_candidates_evaluated=total_candidates,
        exact_replay_count=total_exact_replays,
        approximate_replay_count=total_approx_replays,
        partial_support_count=total_partial_support,
        optional_step_count=total_optional_steps,
        intra_session_repetition_count=total_intra_reps,
        average_alignment_similarity=avg_alignment,
        candidates_before_filtering=total_candidates_before,
        candidates_after_filtering=total_candidates_after,
        scenario_details=scenario_details,
    )


def validate_workflow_explanations(workflows: List[DiscoveredWorkflow]) -> Dict[str, Any]:
    """
    Validates that each discovered workflow's structured explanation is present,
    mathematically grounded in the underlying metrics, and free of hallucinated steps.
    """
    total = len(workflows)
    validated = 0
    checks_passed = 0
    total_checks = 0

    for wf in workflows:
        if not wf.explanation:
            continue
        exp = wf.explanation

        # Check 1: Session counts match
        total_checks += 1
        if exp.occurrence_evidence.distinct_sessions_observed == wf.occurrences:
            checks_passed += 1

        # Check 2: Sequence length matches
        total_checks += 1
        if exp.sequence_evidence.sequence_length == len(wf.sequence):
            checks_passed += 1

        # Check 3: Alignment score matches
        total_checks += 1
        if abs(exp.sequence_evidence.average_alignment_score - wf.similarity) < 0.001:
            checks_passed += 1

        # Check 4: Confidence score matches
        total_checks += 1
        if abs(exp.confidence_factors.score - wf.confidence) < 0.001:
            checks_passed += 1

        # Check 5: Ranking score matches
        if wf.ranking_score is not None:
            total_checks += 1
            if abs(exp.ranking_factors.score - wf.ranking_score) < 0.001:
                checks_passed += 1

        # Check 6: Quality tier matches
        if wf.quality_tier is not None:
            total_checks += 1
            if exp.ranking_factors.tier == wf.quality_tier:
                checks_passed += 1

        # Check 7: Canonical sequence matches exactly
        total_checks += 1
        if exp.sequence_evidence.canonical_sequence == wf.sequence:
            checks_passed += 1

        # Check 8: Limitations present
        total_checks += 1
        if len(exp.limitations) >= 2:
            checks_passed += 1

        validated += 1

    return {
        "workflows_evaluated": total,
        "workflows_with_explanations": validated,
        "checks_passed": checks_passed,
        "total_checks": total_checks,
        "explainability_validity_rate": (checks_passed / total_checks) if total_checks > 0 else 1.0,
    }


if __name__ == "__main__":
    benchmark_33 = build_phase8_5_benchmark_dataset()

    print("=================================================================================================================")
    print("      WORKFLOWOS DISCOVERY BENCHMARK: PHASE 8.1 vs PHASE 8.2 vs PHASE 8.3/8.4 vs PHASE 8.5 ROBUST DISCOVERY      ")
    print("=================================================================================================================")

    # 1. Baseline Phase 8.1 detector on full 33-scenario dataset
    legacy_detector = LegacyPhase81Detector()
    report_legacy = evaluate_discovery_engine(detector=legacy_detector, dataset=benchmark_33)

    # 2. Phase 8.2 local alignment detector on full 33-scenario dataset
    p82_detector = RepetitionDetector(min_length=3, min_occurrences=2, similarity_threshold=0.8)
    report_p82 = evaluate_discovery_engine(detector=p82_detector, dataset=benchmark_33)

    # 3. Phase 8.3/8.4 detector with ranking & noise reduction
    p83_ranked = RepetitionDetector(
        min_length=3,
        min_occurrences=2,
        similarity_threshold=0.8,
        filter_noise=True,
        min_ranking_score=0.70,
    )
    report_p83 = evaluate_discovery_engine(detector=p83_ranked, dataset=benchmark_33)

    # 4. Phase 8.5 detector with robustness, optional steps, partial execution & intra-session reps
    p85_detector = RepetitionDetector(
        min_length=3,
        min_occurrences=2,
        similarity_threshold=0.8,
        filter_noise=True,
        min_ranking_score=0.70,
    )
    report_p85 = evaluate_discovery_engine(detector=p85_detector, dataset=benchmark_33)

    print(f"Dataset Size: {len(benchmark_33)} Scenarios (8 P8.1 + 8 P8.2 + 8 P8.3 + 9 P8.5)")
    print(f"")
    print(f"{'Metric':<32} | {'Phase 8.1':<12} | {'Phase 8.2':<12} | {'Phase 8.3/8.4':<14} | {'Phase 8.5':<12}")
    print(f"{'-'*32}|{'-'*14}|{'-'*14}|{'-'*16}|{'-'*14}")
    print(f"{'Precision':<32} | {report_legacy.precision:<12.4f} | {report_p82.precision:<12.4f} | {report_p83.precision:<14.4f} | {report_p85.precision:<12.4f}")
    print(f"{'Recall':<32} | {report_legacy.recall:<12.4f} | {report_p82.recall:<12.4f} | {report_p83.recall:<14.4f} | {report_p85.recall:<12.4f}")
    print(f"{'F1 Score':<32} | {report_legacy.f1_score:<12.4f} | {report_p82.f1_score:<12.4f} | {report_p83.f1_score:<14.4f} | {report_p85.f1_score:<12.4f}")
    print(f"{'True Positives (TP)':<32} | {report_legacy.true_positives:<12} | {report_p82.true_positives:<12} | {report_p83.true_positives:<14} | {report_p85.true_positives:<12}")
    print(f"{'False Positives (FP)':<32} | {report_legacy.false_positives:<12} | {report_p82.false_positives:<12} | {report_p83.false_positives:<14} | {report_p85.false_positives:<12}")
    print(f"{'False Negatives (FN)':<32} | {report_legacy.false_negatives:<12} | {report_p82.false_negatives:<12} | {report_p83.false_negatives:<14} | {report_p85.false_negatives:<12}")
    print(f"{'True Negatives (TN)':<32} | {report_legacy.true_negatives:<12} | {report_p82.true_negatives:<12} | {report_p83.true_negatives:<14} | {report_p85.true_negatives:<12}")
    print(f"{'Accuracy':<32} | {report_legacy.accuracy:<12.4f} | {report_p82.accuracy:<12.4f} | {report_p83.accuracy:<14.4f} | {report_p85.accuracy:<12.4f}")
    print(f"{'Duplicates Suppressed':<32} | {report_legacy.duplicate_suppressions:<12} | {report_p82.duplicate_suppressions:<12} | {report_p83.duplicate_suppressions:<14} | {report_p85.duplicate_suppressions:<12}")
    print(f"{'-'*32}|{'-'*14}|{'-'*14}|{'-'*16}|{'-'*14}")
    print(f"{'Exact Replay Count':<32} | {report_legacy.exact_replay_count:<12} | {report_p82.exact_replay_count:<12} | {report_p83.exact_replay_count:<14} | {report_p85.exact_replay_count:<12}")
    print(f"{'Approximate Replay Count':<32} | {report_legacy.approximate_replay_count:<12} | {report_p82.approximate_replay_count:<12} | {report_p83.approximate_replay_count:<14} | {report_p85.approximate_replay_count:<12}")
    print(f"{'Partial Support Count':<32} | {report_legacy.partial_support_count:<12} | {report_p82.partial_support_count:<12} | {report_p83.partial_support_count:<14} | {report_p85.partial_support_count:<12}")
    print(f"{'Optional-Step Count':<32} | {report_legacy.optional_step_count:<12} | {report_p82.optional_step_count:<12} | {report_p83.optional_step_count:<14} | {report_p85.optional_step_count:<12}")
    print(f"{'Intra-Session Repetitions':<32} | {report_legacy.intra_session_repetition_count:<12} | {report_p82.intra_session_repetition_count:<12} | {report_p83.intra_session_repetition_count:<14} | {report_p85.intra_session_repetition_count:<12}")
    print(f"{'Avg Alignment Similarity':<32} | {report_legacy.average_alignment_similarity:<12.4f} | {report_p82.average_alignment_similarity:<12.4f} | {report_p83.average_alignment_similarity:<14.4f} | {report_p85.average_alignment_similarity:<12.4f}")
    print(f"{'Candidates Before Filtering':<32} | {report_legacy.candidates_before_filtering:<12} | {report_p82.candidates_before_filtering:<12} | {report_p83.candidates_before_filtering:<14} | {report_p85.candidates_before_filtering:<12}")
    print(f"{'Candidates After Filtering':<32} | {report_legacy.candidates_after_filtering:<12} | {report_p82.candidates_after_filtering:<12} | {report_p83.candidates_after_filtering:<14} | {report_p85.candidates_after_filtering:<12}")
    print("=================================================================================================================")

    # Explainability Audit across all discovered workflows
    all_discovered_workflows: List[DiscoveredWorkflow] = []
    for sc in benchmark_33:
        res = p85_detector.detect(sc.session_sequences, include_suppressed=True)
        all_discovered_workflows.extend(res.workflows)

    audit_res = validate_workflow_explanations(all_discovered_workflows)
    print("\nPhase 8.5 Explainability Verification Audit:")
    print(f"  Total Workflows Evaluated:          {audit_res['workflows_evaluated']}")
    print(f"  Workflows With Valid Explanations:  {audit_res['workflows_with_explanations']}")
    print(f"  Explainability Evidence Checks:     {audit_res['checks_passed']}/{audit_res['total_checks']} passed ({audit_res['explainability_validity_rate']*100:.1f}%)")

    print("\n-----------------------------------------------------------------------------------------------------------------")
    print("Sample Phase 8.5 Robust Discoveries with Evidence Breakdown:")
    for sc_id in [
        "scenario_25_optional_step_omission",
        "scenario_26_intermediate_bounded_noise",
        "scenario_27_partial_execution_tracking",
        "scenario_28_variable_workflow_positions",
        "scenario_29_intra_session_repetition",
    ]:
        matching_sc = next(s for s in benchmark_33 if s.scenario_id == sc_id)
        res = p85_detector.detect(matching_sc.session_sequences, include_suppressed=True)
        print(f"\nScenario: {matching_sc.name}")
        for wf in res.workflows:
            print(f"  -> Discovered: {wf.label} (Rank #{wf.rank}, {wf.quality_tier})")
            print(f"     Summary:          {wf.explanation.summary if wf.explanation else 'N/A'}")
            print(f"     Detection Reason: {wf.explanation.detection_reason if wf.explanation else 'N/A'}")
            print(f"     Optional Steps:   {wf.optional_steps}")
            print(f"     Partial Support:  {wf.partial_support_count} sessions")
            print(f"     Intra-Session:    {wf.intra_session_repetitions} repetitions")
            if wf.explanation:
                print(f"     Fidelity:         {wf.explanation.sequence_evidence.variations_summary}")
                print(f"     Consistency:      {wf.explanation.consistency_evidence.consistency_description}")
                print(f"     Drivers:          {', '.join(wf.explanation.ranking_factors.primary_drivers)}")
                print(f"     Limitations:      {wf.explanation.limitations[0]}")
    print("=================================================================================================================")

