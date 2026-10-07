/**
 * WorkFlowOS Centralized API Client (Phase 14 Productization)
 *
 * Provides strongly-typed, error-resilient client wrappers for all backend APIs:
 * - System telemetry, status, onboarding, and safe settings
 * - Ingested activity events
 * - Workflow discovery, learning, automation planning, and closed-loop intelligence
 * - Declarative workflow definition and execution
 * - Ecosystem applications & capability registries
 * - Privacy controls, collection toggles, and retention audits
 *
 * Security & Reliability:
 * - Never returns raw exceptions or stack traces to UI callers.
 * - Centralizes error formatting into clean, user-facing messages.
 */

import {
  ActivityEvent,
  EmitActivityEventParams,
  DiscoveryResult,
  WorkflowDefinition,
  WorkflowLearningState,
  AutomationPlanResponse,
  ClosedLoopSummary,
  WorkflowExecutionOutcome,
  AutomationExecutionRecord,
  ExecuteWorkflowResponse,
  ApplicationSummary,
  ApplicationCapability,
  ApplicationHealth,
  IntegrationSummaryItem,
  SystemStatusResponse,
  OnboardingResponse,
  SystemSettingsResponse,
  PrivacyStatusResponse,
} from "./types";
import { API_BASE_URL, formatApiErrorMessage } from "./utils";

class ApiClientError extends Error {
  statusCode?: number;
  constructor(message: string, statusCode?: number) {
    super(message);
    this.name = "ApiClientError";
    this.statusCode = statusCode;
  }
}

async function handleResponse<T>(res: Response, fallbackError: string): Promise<T> {
  if (!res.ok) {
    let errDetail: unknown = null;
    try {
      errDetail = await res.json();
    } catch {
      // Body is not JSON
    }
    const message = formatApiErrorMessage(errDetail, `${fallbackError} (${res.status})`);
    throw new ApiClientError(message, res.status);
  }
  return res.json() as Promise<T>;
}

// ----------------------------------------------------------------------------
// 1. System & Onboarding APIs
// ----------------------------------------------------------------------------

export async function fetchSystemStatus(): Promise<SystemStatusResponse> {
  const res = await fetch(`${API_BASE_URL}/api/system/status`, { cache: "no-store" });
  return handleResponse<SystemStatusResponse>(res, "Unable to load system status");
}

export async function fetchSystemOnboarding(): Promise<OnboardingResponse> {
  const res = await fetch(`${API_BASE_URL}/api/system/onboarding`, { cache: "no-store" });
  return handleResponse<OnboardingResponse>(res, "Unable to load onboarding checklist");
}

export async function fetchSystemSettings(): Promise<SystemSettingsResponse> {
  const res = await fetch(`${API_BASE_URL}/api/system/settings`, { cache: "no-store" });
  return handleResponse<SystemSettingsResponse>(res, "Unable to load system settings");
}

export async function checkBackendHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE_URL}/health`, { cache: "no-store" });
    return res.ok;
  } catch {
    return false;
  }
}

// ----------------------------------------------------------------------------
// 2. Activity Events APIs
// ----------------------------------------------------------------------------

export async function fetchEvents(params?: {
  limit?: number;
  session_id?: string;
  application?: string;
}): Promise<ActivityEvent[]> {
  const query = new URLSearchParams();
  if (params?.limit) query.set("limit", String(params.limit));
  if (params?.session_id) query.set("session_id", params.session_id);
  if (params?.application) query.set("application", params.application);

  const qs = query.toString() ? `?${query.toString()}` : "";
  const res = await fetch(`${API_BASE_URL}/api/events${qs}`, { cache: "no-store" });
  return handleResponse<ActivityEvent[]>(res, "Unable to retrieve activity events");
}

/**
 * Returns a stable demo session ID for the current browser tab.
 * Persisted in sessionStorage so the Email, CRM, and Chat demo routes
 * share the exact same session ID for multi-step workflow discovery.
 */
export function getDemoSessionId(): string {
  if (typeof window === "undefined" || !window.sessionStorage) {
    return "workflowos_demo_session_static";
  }
  const SESSION_KEY = "workflowos_demo_session_id";
  try {
    let sessionId = window.sessionStorage.getItem(SESSION_KEY);
    if (!sessionId) {
      const rand =
        typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
          ? crypto.randomUUID().slice(0, 8)
          : Math.random().toString(36).substring(2, 10);
      sessionId = `workflowos_demo_session_${rand}`;
      window.sessionStorage.setItem(SESSION_KEY, sessionId);
    }
    return sessionId;
  } catch {
    return "workflowos_demo_session_fallback";
  }
}

/**
 * Emits a semantic activity event to the FastAPI backend (/api/events).
 *
 * Used by controlled demo applications (Email, CRM, Chat) to report user actions.
 * - POSTs to /api/events, which executes through the backend privacy gate.
 * - Reuses NEXT_PUBLIC_API_URL via API_BASE_URL.
 * - Returns success/failure to the caller without crashing the UI.
 * - Logs a development-safe warning if event ingestion fails.
 * - Does not expose sensitive credentials.
 */
export async function emitActivityEvent(
  params: EmitActivityEventParams
): Promise<{ success: boolean; event?: ActivityEvent; error?: string }> {
  try {
    const payload = {
      session_id: params.session_id || getDemoSessionId(),
      timestamp: params.timestamp || new Date().toISOString(),
      application: params.application,
      event_type: params.event_type,
      target: params.target ?? "customer_request",
      metadata: params.metadata || {},
    };

    const res = await fetch(`${API_BASE_URL}/api/events`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      let errDetail: unknown = null;
      try {
        errDetail = await res.json();
      } catch {
        // Body is not JSON
      }
      const message = formatApiErrorMessage(errDetail, `Event ingestion rejected (${res.status})`);
      if (process.env.NODE_ENV !== "production") {
        console.warn(`[WorkFlowOS] Activity event emission warning: ${message}`);
      }
      return { success: false, error: message };
    }

    const createdEvent = (await res.json()) as ActivityEvent;
    return { success: true, event: createdEvent };
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    if (process.env.NODE_ENV !== "production") {
      console.warn(`[WorkFlowOS] Failed to emit activity event: ${message}`);
    }
    return { success: false, error: message };
  }
}

// ----------------------------------------------------------------------------
// 3. Workflow Discovery & Lifecycle APIs
// ----------------------------------------------------------------------------

export async function fetchDiscoveredWorkflows(includeSuppressed = true): Promise<DiscoveryResult> {
  const res = await fetch(
    `${API_BASE_URL}/api/discovery/repeated?include_suppressed=${includeSuppressed}`,
    { cache: "no-store" }
  );
  return handleResponse<DiscoveryResult>(res, "Unable to detect workflow patterns");
}

export async function fetchDeclarativeWorkflows(): Promise<WorkflowDefinition[]> {
  const res = await fetch(`${API_BASE_URL}/api/automation/workflows`, { cache: "no-store" });
  return handleResponse<WorkflowDefinition[]>(res, "Unable to load declarative workflows");
}

export async function fetchWorkflowLearningState(workflowId: string): Promise<WorkflowLearningState> {
  const res = await fetch(`${API_BASE_URL}/api/workflows/${encodeURIComponent(workflowId)}/learning`, {
    cache: "no-store",
  });
  return handleResponse<WorkflowLearningState>(res, "Unable to load workflow learning state");
}

export async function submitWorkflowFeedback(
  workflowId: string,
  decision: "approve" | "reject" | "edit_approve",
  payload?: {
    rejection_reason?: string;
    edited_workflow?: Record<string, unknown>;
    original_workflow?: Record<string, unknown>;
  }
): Promise<{ success: boolean; learning_state: WorkflowLearningState; message: string }> {
  const res = await fetch(`${API_BASE_URL}/api/workflows/${encodeURIComponent(workflowId)}/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      decision,
      rejection_reason: payload?.rejection_reason,
      edited_workflow: payload?.edited_workflow,
      original_workflow: payload?.original_workflow,
    }),
  });
  return handleResponse(res, "Unable to record workflow feedback");
}

export async function deleteWorkflow(
  workflowId: string
): Promise<{ success: boolean; workflow_id: string; message: string }> {
  const res = await fetch(`${API_BASE_URL}/api/workflows/${encodeURIComponent(workflowId)}`, {
    method: "DELETE",
  });
  return handleResponse(res, "Unable to delete workflow");
}


export async function generateAutomationPlan(
  workflowId: string,
  workflowName: string,
  steps: { id: string; action: string; application: string }[]
): Promise<AutomationPlanResponse> {
  const res = await fetch(`${API_BASE_URL}/api/workflows/${encodeURIComponent(workflowId)}/automation-plan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      steps,
      workflow_name: workflowName,
    }),
  });
  return handleResponse<AutomationPlanResponse>(res, "Unable to generate automation plan");
}

export async function fetchClosedLoopSummary(workflowId: string): Promise<ClosedLoopSummary> {
  const res = await fetch(
    `${API_BASE_URL}/api/workflows/${encodeURIComponent(workflowId)}/closed-loop-summary`,
    { cache: "no-store" }
  );
  return handleResponse<ClosedLoopSummary>(res, "Unable to retrieve closed-loop summary");
}

export async function fetchWorkflowOutcomes(
  workflowId: string,
  limit = 20
): Promise<WorkflowExecutionOutcome[]> {
  const res = await fetch(
    `${API_BASE_URL}/api/workflows/${encodeURIComponent(workflowId)}/outcomes?limit=${limit}`,
    { cache: "no-store" }
  );
  return handleResponse<WorkflowExecutionOutcome[]>(res, "Unable to retrieve workflow execution outcomes");
}

// ----------------------------------------------------------------------------
// 4. Execution APIs
// ----------------------------------------------------------------------------

export async function fetchExecutions(): Promise<AutomationExecutionRecord[]> {
  const res = await fetch(`${API_BASE_URL}/api/automation/executions`, { cache: "no-store" });
  const data = await handleResponse<{ executions: AutomationExecutionRecord[] }>(
    res,
    "Unable to load executions"
  );
  return (data.executions || []).reverse();
}

export async function executeWorkflow(payload: {
  workflow_definition?: WorkflowDefinition;
  proposal?: unknown;
  actions?: { type: string; application: string; description: string; target: string }[];
  approved: boolean;
  executor_type?: string;
  parameters?: Record<string, unknown>;
}): Promise<ExecuteWorkflowResponse> {
  const res = await fetch(`${API_BASE_URL}/api/automation/execute`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handleResponse<ExecuteWorkflowResponse>(res, "Workflow execution failed");
}

export async function resumeExecution(
  executionId: string,
  executorType = "playwright"
): Promise<ExecuteWorkflowResponse> {
  const res = await fetch(`${API_BASE_URL}/api/automation/executions/${executionId}/resume`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ executor_type: executorType }),
  });
  return handleResponse<ExecuteWorkflowResponse>(res, "Unable to resume execution");
}

export async function cancelExecution(executionId: string): Promise<ExecuteWorkflowResponse> {
  const res = await fetch(`${API_BASE_URL}/api/automation/executions/${executionId}/cancel`, {
    method: "POST",
  });
  return handleResponse<ExecuteWorkflowResponse>(res, "Unable to cancel execution");
}

// ----------------------------------------------------------------------------
// 5. Application Ecosystem APIs
// ----------------------------------------------------------------------------

export async function fetchApplications(): Promise<ApplicationSummary[]> {
  const res = await fetch(`${API_BASE_URL}/api/applications`, { cache: "no-store" });
  return handleResponse<ApplicationSummary[]>(res, "Unable to retrieve applications");
}

export async function fetchApplicationDetails(applicationId: string): Promise<ApplicationSummary> {
  const res = await fetch(`${API_BASE_URL}/api/applications/${encodeURIComponent(applicationId)}`, {
    cache: "no-store",
  });
  return handleResponse<ApplicationSummary>(res, `Unable to retrieve application '${applicationId}'`);
}

export async function fetchApplicationCapabilities(
  applicationId: string
): Promise<ApplicationCapability[]> {
  const res = await fetch(
    `${API_BASE_URL}/api/applications/${encodeURIComponent(applicationId)}/capabilities`,
    { cache: "no-store" }
  );
  return handleResponse<ApplicationCapability[]>(
    res,
    `Unable to retrieve capabilities for '${applicationId}'`
  );
}

export async function fetchApplicationHealth(applicationId: string): Promise<ApplicationHealth> {
  const res = await fetch(
    `${API_BASE_URL}/api/applications/${encodeURIComponent(applicationId)}/health`,
    { cache: "no-store" }
  );
  return handleResponse<ApplicationHealth>(res, `Unable to check health for '${applicationId}'`);
}

// ----------------------------------------------------------------------------
// 6. Privacy & Safety APIs
// ----------------------------------------------------------------------------

export async function fetchPrivacyStatus(): Promise<PrivacyStatusResponse> {
  const res = await fetch(`${API_BASE_URL}/api/privacy/status`, { cache: "no-store" });
  return handleResponse<PrivacyStatusResponse>(res, "Unable to load privacy status");
}

export async function togglePrivacyCollection(
  enabled: boolean
): Promise<{ collection_enabled: boolean }> {
  const res = await fetch(`${API_BASE_URL}/api/privacy/toggle`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ collection_enabled: enabled }),
  });
  return handleResponse<{ collection_enabled: boolean }>(res, "Unable to update collection policy");
}

export async function triggerRetentionCleanup(
  dryRun = true,
  retentionDays?: number
): Promise<{
  dry_run: boolean;
  retention_days: number;
  cutoff_timestamp: string;
  events_eligible_for_deletion: number;
  deleted_count: number;
}> {
  const res = await fetch(`${API_BASE_URL}/api/privacy/retention/cleanup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dry_run: dryRun, retention_days: retentionDays }),
  });
  return handleResponse(res, "Retention cleanup failed");
}

export async function auditPrivacyPayload(payload: unknown): Promise<{
  contains_sensitive_data: boolean;
  detected_categories: string[];
  redacted_fields: string[];
}> {
  const res = await fetch(`${API_BASE_URL}/api/privacy/audit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ payload }),
  });
  return handleResponse(res, "Privacy audit failed");
}

// ----------------------------------------------------------------------------
// 7. Service Integrations APIs
// ----------------------------------------------------------------------------

export async function fetchIntegrations(): Promise<IntegrationSummaryItem[]> {
  const res = await fetch(`${API_BASE_URL}/api/integrations`, { cache: "no-store" });
  return handleResponse<IntegrationSummaryItem[]>(res, "Unable to load integrations");
}

export async function connectIntegration(
  integrationId: string,
  credentials: Record<string, unknown> = {}
): Promise<unknown> {
  const res = await fetch(`${API_BASE_URL}/api/integrations/${integrationId}/connect`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ credentials }),
  });
  return handleResponse(res, `Failed to connect integration '${integrationId}'`);
}

export async function disconnectIntegration(integrationId: string): Promise<unknown> {
  const res = await fetch(`${API_BASE_URL}/api/integrations/${integrationId}/disconnect`, {
    method: "POST",
  });
  return handleResponse(res, `Failed to disconnect integration '${integrationId}'`);
}

export async function testIntegrationAction(
  integrationId: string,
  action: string,
  parameters: Record<string, unknown> = {}
): Promise<unknown> {
  const res = await fetch(`${API_BASE_URL}/api/integrations/${integrationId}/execute`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, parameters }),
  });
  return handleResponse(res, `Action test failed on '${integrationId}'`);
}
