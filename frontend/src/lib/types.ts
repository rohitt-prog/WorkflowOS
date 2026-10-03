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

export interface DiscoveredWorkflow {
  label: string;
  sequence: string[];
  occurrences: number;
  similarity: number;
  session_ids: string[];
}

export interface DiscoveryResult {
  detected: boolean;
  workflows: DiscoveredWorkflow[];
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

export type ViewId = "dashboard" | "activity" | "discovery" | "builder" | "executions" | "settings";
