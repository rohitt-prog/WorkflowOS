// Shared TypeScript types used across all components

export interface EventMetadata {
  customer?: string;
  customer_name?: string;
  client?: string;
  name?: string;
  subject?: string;
  search_query?: string;
  [key: string]: unknown;
}

export interface ActivityEvent {
  id: string;
  session_id: string;
  timestamp: string;
  application: string;
  event_type: string;
  target?: string | null;
  metadata?: EventMetadata;
}

export interface ConfidenceBreakdown {
  repetition_support: number;
  sequence_similarity: number;
  action_diversity: number;
  sequence_length: number;
  session_consistency: number;
  raw_signals?: Record<string, unknown>;
}

export interface RankingBreakdown {
  pattern_confidence: number;
  execution_fidelity: number;
  operational_volume: number;
  automation_impact: number;
  task_richness: number;
  raw_signals?: Record<string, unknown>;
}

export interface OccurrenceEvidence {
  distinct_sessions_observed: number;
  min_sessions_required: number;
  threshold_satisfied: boolean;
  repetition_description: string;
  intra_session_repetitions?: number;
  partial_support_count?: number;
}

export interface SequenceEvidence {
  canonical_sequence: string[];
  sequence_length: number;
  unique_actions_count: number;
  action_diversity_ratio: number;
  average_alignment_score: number;
  exact_match_sessions_count: number;
  approximate_match_sessions_count: number;
  total_insertions_observed: number;
  total_deletions_observed: number;
  total_transpositions_observed: number;
  optional_steps?: string[];
  max_consecutive_noise_observed?: number;
  variations_summary: string;
}

export interface ConsistencyEvidence {
  exact_replay_percentage: number;
  is_fully_consistent: boolean;
  consistency_description: string;
}

export interface ConfidenceFactorBreakdown {
  score: number;
  tier: string;
  primary_strengths: string[];
  limiting_factors: string[];
}

export interface RankingFactorBreakdown {
  score: number;
  rank?: number | null;
  tier: string;
  primary_drivers: string[];
  limiting_factors: string[];
}

export interface SuppressionEvidence {
  is_suppressed: boolean;
  suppression_reason?: string | null;
  threshold_criterion?: string | null;
  measured_value?: string | null;
  representative_pattern_id?: string | null;
  representative_rationale?: string | null;
}

export interface WorkflowExplanation {
  summary: string;
  detection_reason: string;
  supporting_sessions: string[];
  occurrence_evidence: OccurrenceEvidence;
  sequence_evidence: SequenceEvidence;
  consistency_evidence: ConsistencyEvidence;
  confidence_explanation: string;
  confidence_factors: ConfidenceFactorBreakdown;
  ranking_explanation: string;
  ranking_factors: RankingFactorBreakdown;
  quality_explanation: string;
  suppression_explanation?: string | null;
  suppression_evidence?: SuppressionEvidence | null;
  representative_explanation?: string | null;
  limitations: string[];
  // Phase 8.5 fields
  optional_steps?: string[];
  partial_support_count?: number;
  intra_session_repetitions?: number;
  bounded_noise_tolerance?: string;
}

export interface DiscoveredWorkflow {
  label: string;
  sequence: string[];
  occurrences: number;
  similarity: number;
  session_ids: string[];
  confidence?: number;
  confidence_tier?: "high" | "medium" | "low";
  confidence_breakdown?: ConfidenceBreakdown;
  confidence_explanation?: string;
  // Phase 8.3 Ranking & Duplicate Detection fields
  rank?: number;
  ranking_score?: number;
  quality_tier?: "exceptional" | "strong" | "moderate" | "low";
  ranking_breakdown?: RankingBreakdown;
  ranking_explanation?: string;
  is_duplicate?: boolean;
  representative_pattern_id?: string;
  suppression_reason?: string;
  // Phase 8.4 Explainability fields
  explanation?: WorkflowExplanation;
  // Phase 8.5 Discovery Quality & Robustness fields
  optional_steps?: string[];
  partial_support_count?: number;
  partial_support_session_ids?: string[];
  intra_session_repetitions?: number;
  // Phase 9 Adaptive Learning & Feedback fields
  workflow_id?: string;
  learning_score?: number;
  recommendation_status?: RecommendationStatus;
  learning_explanation?: string;
  learning_state?: WorkflowLearningState;
}

export type RecommendationStatus = "NEW" | "LEARNING" | "RECOMMENDED" | "DEPRIORITIZED";

export type FeedbackDecision = "approve" | "reject" | "edit_approve";

export interface WorkflowFeedback {
  feedback_id: string;
  workflow_id: string;
  decision: FeedbackDecision;
  original_workflow?: Record<string, unknown> | null;
  edited_workflow?: Record<string, unknown> | null;
  rejection_reason?: string | null;
  timestamp: string;
  session_id?: string | null;
  metadata?: Record<string, unknown>;
}

export interface WorkflowLearningState {
  workflow_id: string;
  approval_count: number;
  rejection_count: number;
  edit_count: number;
  execution_count: number;
  successful_execution_count: number;
  failed_execution_count: number;
  intervention_count: number;
  recovery_count: number;
  learning_score: number;
  recommendation_status: RecommendationStatus;
  learning_explanation: string;
  last_feedback?: Record<string, unknown> | null;
  last_execution_status?: string | null;
  last_failed_step?: string | null;
  last_failure_reason?: string | null;
  updated_at: string;
}

export interface DiscoveryResult {
  detected: boolean;
  workflows: DiscoveredWorkflow[];
  suppressed_workflows?: DiscoveredWorkflow[];
  total_candidates_evaluated?: number;
}

export interface WorkflowTrigger {
  type: string;
  application: string;
  description: string;
}

export interface WorkflowAction {
  type: string;
  application: string;
  description: string;
  target: string;
}

export interface WorkflowProposal {
  name: string;
  intent: string;
  description?: string;
  trigger: WorkflowTrigger;
  actions: WorkflowAction[];
  variables: string[];
  applications: string[];
  requires_approval: boolean;
}

export type ApprovalStatus = "idle" | "approved" | "rejected";

export interface AutomationActionStatus {
  action: string;
  status: "completed" | "failed" | "pending";
  message?: string;
  application?: string;
}

export interface ActionDetail {
  action: string;
  action_id?: string;
  action_type?: string;
  description?: string;
  application: string;
  target?: string;
  status: "completed" | "failed" | "skipped" | "pending" | "running";
  message?: string;
}

export interface HumanIntervention {
  title: string;
  reason: string;
  action_required: string;
}

export interface AutomationExecutionResponse {
  status: "completed" | "failed" | "pending" | "paused" | "cancelled";
  workflow_id: string;
  workflow_name?: string;
  failed_action?: string;
  failure_reason?: string;
  message?: string;
  requires_human_intervention?: boolean;
  human_intervention?: HumanIntervention;
  resume_available?: boolean;
  resume_count?: number;
  paused_at?: string;
  resumed_at?: string;
  cancelled_at?: string;
  actions: AutomationActionStatus[];
  completed_actions: string[];
  total_actions: number;
  execution_time_seconds?: number;
  applications?: string[];
  started_at?: string;
  completed_at?: string;
  all_actions?: ActionDetail[];
}

export type ExecuteWorkflowResponse = AutomationExecutionResponse;

export interface AutomationExecutionRecord {
  execution_id: string;
  workflow_name: string;
  status: "completed" | "failed" | "pending" | "running" | "paused" | "cancelled";
  current_action?: string | null;
  failed_action?: string | null;
  failure_reason?: string | null;
  completed_actions: string[];
  total_actions: number;
  error?: string | null;
  requires_human_intervention?: boolean;
  resume_available?: boolean;
  resume_count?: number;
  paused_at?: string;
  resumed_at?: string;
  cancelled_at?: string;
  started_at?: string;
  completed_at?: string;
  execution_time_seconds?: number;
  applications?: string[];
  actions_detail?: ActionDetail[];
  all_actions?: ActionDetail[];
}

// Phase 6 declarative workflow types
export interface StepCondition {
  field?: string;
  variable?: string;
  operator: string;
  value?: unknown;
}

export interface RetryPolicy {
  max_retries?: number;
  max_attempts?: number;
  backoff_seconds?: number;
  delay_seconds?: number;
  backoff?: string;
  retry_on_errors?: string[];
}

export interface WorkflowStep {
  id: string;
  name: string;
  type: string;
  application?: string;
  description?: string;
  target?: string;
  parameters?: Record<string, unknown>;
  condition?: StepCondition;
  on_true?: string | null;
  on_false?: string | null;
  retry?: RetryPolicy;
  retry_policy?: RetryPolicy;
  timeout_seconds?: number;
  continue_on_failure?: boolean;
  output_mapping?: Record<string, string>;
}

export interface WorkflowInput {
  name: string;
  type?: string;
  required?: boolean;
  default?: unknown;
  description?: string;
}

export interface WorkflowDefinition {
  id?: string;
  name: string;
  description?: string;
  version?: string;
  trigger?: {
    type: string;
    application?: string;
    event?: string;
  };
  inputs?: WorkflowInput[];
  variables?: Record<string, unknown>;
  steps: WorkflowStep[];
  requires_approval?: boolean;
  tags?: string[];
}

export type ViewId = "dashboard" | "activity" | "workflows" | "discovery" | "builder" | "executions" | "applications" | "settings";

// Phase 7.1 Integration Foundation types
export interface IntegrationActionParam {
  name: string;
  type: string;
  required: boolean;
  default?: unknown;
  description?: string;
  allowed_values?: unknown[];
}

export interface IntegrationActionDef {
  name: string;
  display_name: string;
  description: string;
  parameters: IntegrationActionParam[];
  required_scopes: string[];
  is_safe: boolean;
  is_mutating?: boolean;
  is_destructive: boolean;
  allow_direct_execution?: boolean;
}

export interface IntegrationSummaryItem {
  id: string;
  name: string;
  description: string;
  version: string;
  category: string;
  icon?: string | null;
  is_mock: boolean;
  disclaimer?: string | null;
  status: "connected" | "disconnected" | "error";
  is_connected: boolean;
  connected_at?: string | null;
  last_error?: string | null;
  actions: IntegrationActionDef[];
}

// Phase 10 Intelligent Automation types
export type AutomationStrategyType = "API" | "INTEGRATION" | "SEMANTIC_UI" | "BROWSER" | "MANUAL";

export interface StrategyScoreBreakdown {
  capability_score: number;
  priority_score: number;
  reliability_score: number;
  learning_score: number;
  credential_score: number;
  failure_penalty: number;
  safety_penalty: number;
  raw_score: number;
  final_score: number;
}

export interface StrategyCandidate {
  strategy: AutomationStrategyType;
  is_available: boolean;
  score: number;
  score_breakdown: StrategyScoreBreakdown;
  selection_reasons: string[];
  rejection_reason?: string | null;
  metadata?: Record<string, unknown>;
}

export interface StepPlan {
  step_id: string;
  action: string;
  application: string;
  description?: string | null;
  selected_strategy: AutomationStrategyType;
  score: number;
  reason: string;
  selected_reasons: string[];
  rejected_strategies: Record<string, string>;
  candidates: StrategyCandidate[];
  fallback_strategy?: AutomationStrategyType | null;
  fallback_reason?: string | null;
  is_mutating: boolean;
  requires_credentials: boolean;
  credentials_available: boolean;
}

export interface AutomationPlan {
  plan_id: string;
  workflow_id: string;
  workflow_name: string;
  selected_strategy: AutomationStrategyType;
  overall_score: number;
  steps: StepPlan[];
  requires_approval: boolean;
  fallback_available: boolean;
  explanation: Record<string, unknown>;
  learning_state_summary?: Record<string, unknown> | null;
  created_at: string;
}

export interface AutomationPlanResponse {
  workflow_id: string;
  plan: AutomationPlan;
  requires_approval: boolean;
  message: string;
}

// ============================================================================
// Phase 11: Closed-Loop Intelligence Types
// ============================================================================

export interface StrategyOutcomeEvidence {
  workflow_id: string;
  step_action: string;
  strategy: string;
  attempts: number;
  successes: number;
  failures: number;
  success_rate: number;
  recent_outcomes: string[];
  recent_successes: number;
  recent_failures: number;
  fallback_count: number;
  last_outcome?: string | null;
  last_failure_category?: string | null;
  last_error_message?: string | null;
  average_duration?: number | null;
  updated_at: string;
}

export interface StepOutcome {
  step_id: string;
  action: string;
  application: string;
  strategy: string;
  status: 'SUCCESS' | 'FAILED' | 'PARTIAL' | 'CANCELLED' | 'PAUSED' | 'NOT_EXECUTED';
  duration_seconds?: number | null;
  retries: number;
  is_fallback: boolean;
  primary_strategy?: string | null;
  failure_category?: string | null;
  error_message?: string | null;
}

export interface WorkflowExecutionOutcome {
  workflow_id: string;
  execution_id: string;
  status: 'SUCCESS' | 'FAILED' | 'PARTIAL' | 'CANCELLED' | 'PAUSED';
  started_at: string;
  completed_at?: string | null;
  duration_seconds?: number | null;
  total_steps: number;
  completed_steps: number;
  failed_steps_count: number;
  unexecuted_steps_count: number;
  failed_step?: string | null;
  failure_category?: string | null;
  fallback_used: boolean;
  step_outcomes: StepOutcome[];
  error_message?: string | null;
}

export interface ClosedLoopSummary {
  workflow_id: string;
  workflow_name: string;
  total_executions: number;
  successful_executions: number;
  failed_executions: number;
  partial_executions: number;
  cancelled_executions: number;
  paused_executions: number;
  strategy_evidence: StrategyOutcomeEvidence[];
  adaptations: string[];
  explanation: string;
}

// Phase 13 Application Ecosystem types
export type ApplicationHealthStatus =
  | "CONNECTED"
  | "DISCONNECTED"
  | "DEGRADED"
  | "UNAVAILABLE"
  | "NOT_CONFIGURED";

export interface ApplicationHealth {
  status: ApplicationHealthStatus;
  connected: boolean;
  message?: string;
  last_checked?: string;
  details?: Record<string, unknown>;
}

export interface ApplicationCapability {
  action_id: string;
  application_id: string;
  display_name: string;
  description: string;
  category: string;
  read_only: boolean;
  mutating: boolean;
  requires_credentials: boolean;
  requires_approval: boolean;
  supported_strategies: string[];
  parameters?: Record<string, unknown>[];
  reliability_metadata?: Record<string, unknown>;
}

export interface ApplicationSummary {
  application_id: string;
  display_name: string;
  integration_type: string;
  connection_status: ApplicationHealthStatus | string;
  health: ApplicationHealth;
  capabilities: ApplicationCapability[];
  supported_actions: string[];
  auth_requirements: string[];
  is_demo: boolean;
  description?: string;
}

// ============================================================================
// Phase 14: Productization & System Telemetry Types
// ============================================================================

export interface ApplicationStatusItem {
  application_id: string;
  display_name: string;
  integration_type: string;
  connected: boolean;
  is_demo: boolean;
  capabilities_count: number;
}

export interface ApplicationsStatusSummary {
  connected: number;
  available: number;
  items: ApplicationStatusItem[];
}

export interface WorkflowsStatusSummary {
  discovered: number;
  declarative: number;
}

export interface ExecutionsStatusSummary {
  total: number;
  successful: number;
  failed: number;
}

export interface PrivacyStatusSummary {
  collection_enabled: boolean;
  retention_days: number;
  redaction_active: boolean;
  human_approval_required: boolean;
}

export interface SystemStatusResponse {
  backend: string;
  agent: "connected" | "disconnected" | "degraded" | string;
  agent_details?: {
    process_id?: number | null;
    mode?: string;
    [key: string]: unknown;
  } | null;
  applications: ApplicationsStatusSummary;
  workflows: WorkflowsStatusSummary;
  executions: ExecutionsStatusSummary;
  privacy: PrivacyStatusSummary;
}

export interface OnboardingStep {
  id: string;
  title: string;
  status: "ready" | "connected" | "protected" | "waiting" | string;
  description: string;
  action_label?: string | null;
  action_target?: ViewId | string | null;
}

export interface OnboardingResponse {
  completed: boolean;
  title: string;
  subtitle: string;
  steps: OnboardingStep[];
}

export interface SystemSettingsResponse {
  backend_url: string;
  frontend_url: string;
  environment: string;
  activity_collection: string;
  event_retention_days: number;
  privacy_posture: string;
  credentials_configured: Record<string, string>;
  guarantees: Record<string, string>;
}

export interface PrivacyStatusResponse {
  collection_enabled: boolean;
  retention_days: number;
  retention_cutoff_timestamp?: string;
  redaction_active: boolean;
  zero_credentials_persisted: boolean;
  approval_gate_required: boolean;
}
