"use client";

import React, { useState } from "react";
import {
  WorkflowDefinition,
  AutomationExecutionResponse,
  AutomationExecutionRecord,
} from "@/lib/types";
import { getApplicationDisplayName } from "@/lib/utils";

export type StepVisualStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "paused"
  | "cancelled"
  | "skipped";

export interface WorkflowVisualizerStep {
  id: string;
  name: string;
  action: string;
  application: string;
  status: StepVisualStatus;
  description?: string;
  target?: string;
  parameters?: Record<string, unknown>;
  errorMessage?: string;
  durationSeconds?: number;
  timestamp?: string;
  humanIntervention?: {
    title: string;
    reason: string;
    action_required: string;
  };
  retryAttempts?: number;
  condition?: string;
}

export interface WorkflowVisualizerProps {
  workflowId?: string;
  workflowName?: string;
  sequence?: string[];
  definition?: WorkflowDefinition | null;
  steps?: WorkflowVisualizerStep[];
  execution?: AutomationExecutionResponse | AutomationExecutionRecord | null;
  isExecuting?: boolean;
  className?: string;
  compact?: boolean;
}

/**
 * Canonical 6-step Gmail -> CRM -> Chat declarative pipeline definition.
 */
export const GMAIL_TRIAGE_PIPELINE_DEF: WorkflowDefinition = {
  id: "wf_gmail_triage_pipeline",
  name: "Gmail Inbox Triage & Customer Lookup",
  description:
    "Reads emails with attachments from Gmail, downloads attachments, cross-references CRM, updates customer records, and notifies team chat.",
  version: "1.0.0",
  trigger: {
    type: "manual",
    application: "gmail",
    event: "inbox_inquiry_received",
  },
  inputs: [
    {
      name: "query",
      type: "string",
      default: "has:attachment",
      required: false,
      description: "Gmail search query filter",
    },
    {
      name: "max_messages",
      type: "integer",
      default: 5,
      required: false,
      description: "Maximum number of messages to fetch (1-20)",
    },
  ],
  steps: [
    {
      id: "step_search_email",
      name: "Search Gmail messages",
      type: "search_messages",
      application: "gmail",
      description: "Search recent emails matching query with attachments",
      parameters: {
        query: "{{inputs.query}}",
        max_results: "{{inputs.max_messages}}",
      },
      output_mapping: { retrieved_count: "data.count" },
      retry_policy: { max_attempts: 2, delay_seconds: 1 },
    },
    {
      id: "step_read_email",
      name: "Read the email",
      type: "read_message",
      application: "gmail",
      description: "Retrieve sender headers, snippet, and attachment metadata",
      parameters: {
        message_id: "{{steps.step_search_email.data.messages[0].id}}",
      },
      retry_policy: { max_attempts: 2, delay_seconds: 1 },
    },
    {
      id: "step_download_attachment",
      name: "Download the attachment",
      type: "download_attachment",
      application: "gmail",
      description: "Download message attachment and compute integrity hash (SHA-256)",
      parameters: {
        message_id: "{{steps.step_read_email.data.id}}",
        attachment_id: "{{steps.step_read_email.data.attachments[0].attachment_id}}",
        filename: "{{steps.step_read_email.data.attachments[0].filename}}",
      },
      retry_policy: { max_attempts: 2, delay_seconds: 1 },
    },
    {
      id: "step_search_crm",
      name: "Search for the CRM customer",
      type: "search_customer",
      application: "crm",
      description: "Query customer profile in CRM using sender information",
      parameters: { query: "{{steps.step_read_email.data.from}}" },
      continue_on_failure: false,
    },
    {
      id: "step_update_crm",
      name: "Update the CRM customer",
      type: "update_customer",
      application: "crm",
      description: "Update customer record with verified attachment hash and active status",
      parameters: {
        customer_id: "{{steps.step_search_crm.data.customer.id}}",
        notes: "Attachment verified (SHA-256)",
        status: "Verified",
      },
      continue_on_failure: false,
    },
    {
      id: "step_send_chat",
      name: "Send the Chat notification",
      type: "send_message",
      application: "chat",
      description: "Notify team workspace that inquiry was triaged and customer updated",
      parameters: {
        channel: "general",
        message:
          "Inquiry from sender triaged. Attachment verified. CRM updated.",
      },
      continue_on_failure: false,
    },
  ],
  requires_approval: true,
  tags: ["gmail", "crm", "chat", "production-workflow"],
};

// Application SVG Icon component
function ApplicationIcon({ app }: { app: string }) {
  const norm = app.toLowerCase();

  if (norm.includes("gmail") || norm === "demo_email" || norm.includes("mail")) {
    return (
      <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
      </svg>
    );
  }

  if (norm.includes("crm") || norm.includes("customer")) {
    return (
      <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
      </svg>
    );
  }

  if (norm.includes("chat") || norm.includes("slack")) {
    return (
      <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
      </svg>
    );
  }

  // Default Action Icon
  return (
    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
    </svg>
  );
}

// Map Application to Styling Badges
function getAppBadgeClasses(app: string): {
  badge: string;
  iconText: string;
} {
  const norm = app.toLowerCase();
  if (norm.includes("gmail") || norm === "demo_email") {
    return {
      badge:
        "bg-rose-50 dark:bg-rose-950/40 border-rose-200 dark:border-rose-800/60 text-rose-700 dark:text-rose-300",
      iconText: "text-rose-600 dark:text-rose-400",
    };
  }
  if (norm.includes("crm")) {
    return {
      badge:
        "bg-sky-50 dark:bg-sky-950/40 border-sky-200 dark:border-sky-800/60 text-sky-700 dark:text-sky-300",
      iconText: "text-sky-600 dark:text-sky-400",
    };
  }
  if (norm.includes("chat")) {
    return {
      badge:
        "bg-emerald-50 dark:bg-emerald-950/40 border-emerald-200 dark:border-emerald-800/60 text-emerald-700 dark:text-emerald-300",
      iconText: "text-emerald-600 dark:text-emerald-400",
    };
  }
  return {
    badge:
      "bg-slate-100 dark:bg-[#1E293B] border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300",
    iconText: "text-slate-600 dark:text-slate-400",
  };
}

/**
 * Matches an execution action or ID to a workflow step type/id with semantic synonyms.
 */
export function matchStepAction(
  step: { id: string; type: string; name?: string },
  actionName?: string | null
): boolean {
  if (!actionName) return false;
  const a = actionName.toLowerCase().trim();
  const stType = step.type?.toLowerCase().trim() || "";
  const stId = step.id?.toLowerCase().trim() || "";
  const stName = step.name?.toLowerCase().trim() || "";

  if (a === stType || a === stId || a === stName) return true;

  const synonyms: Record<string, string[]> = {
    search_messages: [
      "search_messages",
      "list_recent_messages",
      "search_email",
      "step_search_email",
    ],
    read_message: [
      "read_message",
      "open_email",
      "read_email",
      "step_read_email",
    ],
    download_attachment: [
      "download_attachment",
      "step_download_attachment",
    ],
    search_customer: [
      "search_customer",
      "step_search_crm",
    ],
    update_customer: [
      "update_customer",
      "step_update_crm",
    ],
    send_message: [
      "send_message",
      "send_chat",
      "send_chat_message",
      "step_send_chat",
    ],
  };

  for (const [canonical, list] of Object.entries(synonyms)) {
    const stepBelongs = stType === canonical || list.includes(stType) || list.includes(stId);
    if (stepBelongs && list.includes(a)) {
      return true;
    }
  }

  return false;
}

/**
 * Maps a step visual status to a restrained badge configuration.
 */
export function getStepStatusBadge(status: StepVisualStatus): {
  label: string;
  className: string;
  dot?: string;
  icon: string;
} {
  switch (status) {
    case "completed":
      return {
        label: "Completed",
        className:
          "bg-emerald-50 dark:bg-emerald-950/40 border-emerald-200 dark:border-emerald-800/60 text-emerald-700 dark:text-emerald-300",
        dot: "bg-emerald-500",
        icon: "✓",
      };
    case "running":
      return {
        label: "Running",
        className:
          "bg-blue-50 dark:bg-blue-950/40 border-blue-200 dark:border-blue-800/60 text-blue-700 dark:text-blue-300",
        dot: "bg-blue-500 animate-pulse",
        icon: "⟳",
      };
    case "failed":
      return {
        label: "Failed",
        className:
          "bg-rose-50 dark:bg-rose-950/40 border-rose-200 dark:border-rose-800/60 text-rose-700 dark:text-rose-300",
        dot: "bg-rose-500",
        icon: "✕",
      };
    case "paused":
      return {
        label: "Paused",
        className:
          "bg-amber-50 dark:bg-amber-950/40 border-amber-200 dark:border-amber-800/60 text-amber-700 dark:text-amber-300",
        dot: "bg-amber-500",
        icon: "⏸",
      };
    case "cancelled":
      return {
        label: "Cancelled",
        className:
          "bg-slate-100 dark:bg-slate-800/60 border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300",
        dot: "bg-slate-400",
        icon: "⊘",
      };
    case "skipped":
      return {
        label: "Not Executed",
        className:
          "bg-slate-50 dark:bg-slate-800/40 border-slate-200 dark:border-slate-700/60 text-slate-500 dark:text-slate-400 border-dashed",
        dot: "bg-slate-400",
        icon: "↷",
      };
    case "pending":
    default:
      return {
        label: "Pending",
        className:
          "bg-slate-50 dark:bg-slate-900/40 border-slate-200 dark:border-slate-800 text-slate-500 dark:text-slate-400",
        dot: "bg-slate-300 dark:bg-slate-600",
        icon: "○",
      };
  }
}

export default function WorkflowVisualizer({
  workflowId,
  workflowName,
  sequence,
  definition,
  steps: explicitSteps,
  execution,
  isExecuting = false,
  className = "",
  compact = false,
}: WorkflowVisualizerProps) {
  const [selectedStepId, setSelectedStepId] = useState<string | null>(null);
  const [displayMode, setDisplayMode] = useState<"auto" | "pipeline" | "timeline">("auto");

  // Determine base step list
  const derivedSteps: WorkflowVisualizerStep[] = React.useMemo(() => {
    if (explicitSteps && explicitSteps.length > 0) {
      return explicitSteps;
    }

    const isGmailTriage =
      workflowId === "wf_gmail_triage_pipeline" ||
      (workflowName && workflowName.toLowerCase().includes("gmail")) ||
      (sequence && sequence.some((s) => s.includes("list_recent_messages") || s.includes("search_messages")));

    const baseDef: WorkflowDefinition =
      definition ||
      (isGmailTriage
        ? GMAIL_TRIAGE_PIPELINE_DEF
        : {
            id: workflowId || "wf_custom",
            name: workflowName || "Workflow Pipeline",
            steps: (sequence || []).map((action, idx) => ({
              id: `step_${idx + 1}`,
              name: action
                .split("_")
                .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
                .join(" "),
              type: action,
              application: action.includes("email")
                ? "demo_email"
                : action.includes("customer") || action.includes("crm")
                ? "demo_crm"
                : action.includes("chat")
                ? "demo_chat"
                : "app",
              description: `Automated ${action.replace(/_/g, " ")} step`,
            })),
          });

    return baseDef.steps.map((st, idx) => {
      let status: StepVisualStatus = "pending";
      let errMsg: string | undefined;

      if (execution) {
        const completedList = execution.completed_actions || [];
        const actionsDetail =
          execution.all_actions ||
          ("actions_detail" in execution ? execution.actions_detail : []) ||
          [];

        const detailMatch = actionsDetail.find(
          (d) =>
            matchStepAction(st, d.action) ||
            (d.action_id && matchStepAction(st, d.action_id)) ||
            (d.action_type && matchStepAction(st, d.action_type))
        );

        const isCompleted =
          completedList.some((act) => matchStepAction(st, act)) ||
          detailMatch?.status === "completed";

        const isFailed =
          (execution.failed_action && matchStepAction(st, execution.failed_action)) ||
          detailMatch?.status === "failed";

        const currentAction = "current_action" in execution ? execution.current_action : undefined;
        const isCurrent = currentAction ? matchStepAction(st, currentAction) : false;

        if (isCompleted) {
          status = "completed";
          if (detailMatch?.message) errMsg = detailMatch.message;
        } else if (execution.status === "paused" && (isFailed || isCurrent)) {
          status = "paused";
          errMsg =
            execution.failure_reason ||
            detailMatch?.message ||
            ("error" in execution ? execution.error || undefined : undefined);
        } else if (execution.status === "cancelled" && (isCurrent || (detailMatch?.status as string) === "cancelled")) {
          status = "cancelled";
          errMsg = detailMatch?.message || "Execution cancelled";
        } else if (detailMatch?.status === "skipped") {
          status = "skipped";
          errMsg = detailMatch.message;
        } else if (detailMatch?.status === "running") {
          status = "running";
          errMsg = detailMatch.message;
        } else if (isFailed) {
          status = "failed";
          errMsg =
            execution.failure_reason ||
            detailMatch?.message ||
            ("error" in execution ? execution.error || undefined : undefined);
        } else if (isCurrent) {
          if (execution.status === "paused") {
            status = "paused";
          } else if (execution.status === "failed") {
            status = "failed";
          } else if (execution.status === "cancelled") {
            status = "cancelled";
          } else if (execution.status === "completed") {
            status = "completed";
          } else {
            status = "running";
          }
        } else if (execution.status === "completed") {
          status = "completed";
        } else if (execution.status === "cancelled" && idx >= completedList.length) {
          status = "skipped";
        } else if (execution.status === "failed" && !isCompleted && !isFailed && status === "pending") {
          status = "skipped";
        }

        const stepDuration =
          detailMatch && "duration_seconds" in detailMatch && typeof detailMatch.duration_seconds === "number"
            ? detailMatch.duration_seconds
            : detailMatch && "execution_time_seconds" in detailMatch && typeof detailMatch.execution_time_seconds === "number"
            ? detailMatch.execution_time_seconds
            : undefined;

        const stepTimestamp =
          detailMatch && "timestamp" in detailMatch && typeof detailMatch.timestamp === "string"
            ? detailMatch.timestamp
            : detailMatch && "started_at" in detailMatch && typeof detailMatch.started_at === "string"
            ? detailMatch.started_at
            : undefined;

        const stepIntervention =
          status === "paused" && "human_intervention" in execution && execution.human_intervention
            ? execution.human_intervention
            : undefined;

        return {
          id: st.id || `step_${idx + 1}`,
          name: st.name || st.type,
          action: st.type,
          application: st.application || "app",
          status,
          description: st.description,
          target: st.target,
          parameters: st.parameters,
          errorMessage: errMsg,
          durationSeconds: stepDuration,
          timestamp: stepTimestamp,
          humanIntervention: stepIntervention,
          retryAttempts: st.retry_policy?.max_attempts || st.retry?.max_retries,
        };
      }

      return {
        id: st.id || `step_${idx + 1}`,
        name: st.name || st.type,
        action: st.type,
        application: st.application || "app",
        status: isExecuting && idx === 0 ? "running" : status,
        description: st.description,
        target: st.target,
        parameters: st.parameters,
        errorMessage: errMsg,
        retryAttempts: st.retry_policy?.max_attempts || st.retry?.max_retries,
      };
    });
  }, [explicitSteps, workflowId, workflowName, sequence, definition, execution, isExecuting]);

  // Overall pipeline progress
  const completedCount = derivedSteps.filter((s) => s.status === "completed").length;
  const isRunningAny = isExecuting || derivedSteps.some((s) => s.status === "running");
  const isFailedAny = derivedSteps.some((s) => s.status === "failed");
  const isPausedAny = derivedSteps.some((s) => s.status === "paused");
  const isCancelledAny = derivedSteps.some((s) => s.status === "cancelled");

  return (
    <div
      className={`bg-white dark:bg-[#111827] border border-[#E2E8F0] dark:border-[#1E293B] rounded-2xl shadow-2xs overflow-hidden transition-colors duration-150 ${className}`}
      role="region"
      aria-label="Workflow Execution Pipeline Visualization"
    >
      {/* Visualizer Top Bar */}
      <div className="px-5 py-3.5 border-b border-[#E2E8F0] dark:border-[#1E293B] bg-[#F8FAFC] dark:bg-[#0B0F17] flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <div className="w-2.5 h-2.5 rounded-full bg-[#2563EB] dark:bg-[#3B82F6]" />
          <div>
            <h3 className="text-xs font-bold text-[#0F172A] dark:text-[#F8FAFC] tracking-tight uppercase">
              {workflowName || definition?.name || "Workflow Pipeline Execution"}
            </h3>
            <p className="text-[11px] text-[#64748B] dark:text-[#94A3B8]">
              {derivedSteps.length} Connected Automation Nodes
            </p>
          </div>
        </div>

        {/* Status Pills and Layout Switcher */}
        <div className="flex items-center gap-2">
          {/* Progress Pill */}
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border bg-white dark:bg-[#162035] border-[#E2E8F0] dark:border-[#1E293B] text-[#0F172A] dark:text-[#F8FAFC]">
            {isFailedAny ? (
              <span className="flex items-center gap-1 text-rose-600 dark:text-rose-400 font-semibold">
                <span className="w-1.5 h-1.5 rounded-full bg-rose-500" />
                Execution Blocked
              </span>
            ) : isPausedAny ? (
              <span className="flex items-center gap-1 text-amber-600 dark:text-amber-400 font-semibold">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
                Paused for Operator
              </span>
            ) : isCancelledAny ? (
              <span className="flex items-center gap-1 text-slate-600 dark:text-slate-400 font-semibold">
                <span className="w-1.5 h-1.5 rounded-full bg-slate-500" />
                Execution Cancelled
              </span>
            ) : isRunningAny ? (
              <span className="flex items-center gap-1 text-blue-600 dark:text-blue-400 font-semibold">
                <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-ping" />
                Executing…
              </span>
            ) : completedCount === derivedSteps.length && derivedSteps.length > 0 ? (
              <span className="flex items-center gap-1 text-emerald-600 dark:text-emerald-400 font-semibold">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                All {derivedSteps.length} Completed
              </span>
            ) : (
              <span className="text-[#64748B] dark:text-[#94A3B8]">
                Ready for Run ({completedCount}/{derivedSteps.length})
              </span>
            )}
          </div>

          {/* Optional Pipeline / Timeline toggle */}
          <div className="hidden sm:flex bg-slate-100 dark:bg-[#1E293B] p-0.5 rounded-lg border border-[#E2E8F0] dark:border-[#1E293B] text-[10px] font-semibold">
            <button
              type="button"
              onClick={() => setDisplayMode("pipeline")}
              className={`px-2 py-0.5 rounded transition cursor-pointer ${
                displayMode === "pipeline" || displayMode === "auto"
                  ? "bg-white dark:bg-[#111827] text-[#0F172A] dark:text-[#F8FAFC] shadow-2xs"
                  : "text-[#64748B] dark:text-[#94A3B8]"
              }`}
            >
              Pipeline
            </button>
            <button
              type="button"
              onClick={() => setDisplayMode("timeline")}
              className={`px-2 py-0.5 rounded transition cursor-pointer ${
                displayMode === "timeline"
                  ? "bg-white dark:bg-[#111827] text-[#0F172A] dark:text-[#F8FAFC] shadow-2xs"
                  : "text-[#64748B] dark:text-[#94A3B8]"
              }`}
            >
              Timeline
            </button>
          </div>
        </div>
      </div>

      {/* Main Graph Content */}
      <div className={`overflow-x-auto ${compact ? "p-3" : "p-5"}`}>
        {displayMode === "timeline" ? (
          // ================= VERTICAL TIMELINE MODE =================
          <div className="space-y-4 max-w-xl mx-auto py-2">
            {derivedSteps.map((step, idx) => {
              const isLast = idx === derivedSteps.length - 1;
              const isSelected = selectedStepId === step.id;
              const appStyles = getAppBadgeClasses(step.application);
              const statusCfg = getStepStatusBadge(step.status);

              return (
                <div key={step.id} className="relative flex items-start gap-3 sm:gap-4">
                  {/* Vertical Spine */}
                  {!isLast && (
                    <div className="absolute left-4 top-8 -bottom-4 w-0.5">
                      {step.status === "completed" && derivedSteps[idx + 1]?.status === "running" ? (
                        <div className="h-full w-full animate-connector-flow" />
                      ) : step.status === "completed" ? (
                        <div className="h-full w-full bg-emerald-400 dark:bg-emerald-600" />
                      ) : (
                        <div className="h-full w-full border-l border-dashed border-slate-300 dark:border-slate-700" />
                      )}
                    </div>
                  )}

                  {/* Step Status Node Avatar */}
                  <div
                    className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold shrink-0 z-10 border transition-all ${
                      step.status === "completed"
                        ? "bg-emerald-500 border-emerald-600 text-white shadow-xs"
                        : step.status === "running"
                        ? "bg-blue-600 border-blue-700 text-white animate-node-pulse shadow-xs"
                        : step.status === "failed"
                        ? "bg-rose-500 border-rose-600 text-white shadow-xs"
                        : step.status === "paused"
                        ? "bg-amber-500 border-amber-600 text-white shadow-xs"
                        : step.status === "cancelled"
                        ? "bg-slate-500 border-slate-600 text-white shadow-xs"
                        : step.status === "skipped"
                        ? "bg-slate-200 dark:bg-slate-800 border-slate-300 dark:border-slate-700 text-slate-500 dark:text-slate-400 border-dashed shadow-xs"
                        : "bg-white dark:bg-[#162035] border-slate-300 dark:border-slate-700 text-slate-500 dark:text-slate-400"
                    }`}
                  >
                    {step.status === "completed" ? (
                      "✓"
                    ) : step.status === "running" ? (
                      <span className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    ) : step.status === "failed" ? (
                      "✕"
                    ) : step.status === "paused" ? (
                      "⏸"
                    ) : step.status === "cancelled" ? (
                      "⊘"
                    ) : step.status === "skipped" ? (
                      "↷"
                    ) : (
                      idx + 1
                    )}
                  </div>

                  {/* Step Card */}
                  <div
                    onClick={() => setSelectedStepId(isSelected ? null : step.id)}
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        setSelectedStepId(isSelected ? null : step.id);
                      }
                    }}
                    role="button"
                    aria-expanded={isSelected}
                    className={`flex-1 p-3.5 rounded-xl border text-left cursor-pointer transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${
                      isSelected
                        ? "border-[#2563EB] dark:border-[#3B82F6] ring-2 ring-[#2563EB]/20 bg-blue-50/20 dark:bg-blue-950/20 shadow-xs"
                        : step.status === "running"
                        ? "border-blue-300 dark:border-blue-700 bg-blue-50/30 dark:bg-blue-950/20"
                        : step.status === "failed"
                        ? "border-rose-300 dark:border-rose-800 bg-rose-50/30 dark:bg-rose-950/20"
                        : step.status === "paused"
                        ? "border-amber-300 dark:border-amber-700 bg-amber-50/30 dark:bg-amber-950/20"
                        : step.status === "skipped"
                        ? "border-dashed border-slate-300 dark:border-slate-800 bg-slate-50/40 dark:bg-slate-900/30 opacity-75"
                        : "border-[#E2E8F0] dark:border-[#1E293B] hover:border-[#CBD5E1] dark:hover:border-[#334155] bg-white dark:bg-[#162035]"
                    }`}
                  >
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-semibold border flex items-center gap-1 shrink-0 ${appStyles.badge}`}>
                          <ApplicationIcon app={step.application} />
                          {getApplicationDisplayName(step.application)}
                        </span>
                        <span className="text-xs font-bold text-[#0F172A] dark:text-[#F8FAFC]">
                          {step.name}
                        </span>
                        <span className="text-[10px] font-mono text-[#64748B] dark:text-[#94A3B8]">
                          #{idx + 1}
                        </span>
                      </div>

                      <div className="flex items-center gap-1.5 self-start sm:self-auto shrink-0 flex-wrap">
                        {typeof step.durationSeconds === "number" && (
                          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded border bg-slate-50 dark:bg-[#0B0F17] border-[#E2E8F0] dark:border-[#1E293B] text-[#64748B] dark:text-[#94A3B8]">
                            {step.durationSeconds.toFixed(2)}s
                          </span>
                        )}
                        {step.timestamp && (
                          <span className="text-[10px] font-mono text-[#64748B] dark:text-[#94A3B8]">
                            {new Date(step.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
                          </span>
                        )}
                        <span className={`inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full border ${statusCfg.className}`}>
                          {statusCfg.dot && <span className={`w-1.5 h-1.5 rounded-full ${statusCfg.dot}`} />}
                          <span>{statusCfg.label}</span>
                        </span>
                      </div>
                    </div>

                    <p className="text-xs text-[#64748B] dark:text-[#94A3B8] mt-1.5 leading-relaxed">
                      {step.description || `Action: ${step.action}`}
                    </p>

                    {/* Step Paused Human Intervention Callout */}
                    {step.status === "paused" && step.humanIntervention && (
                      <div className="mt-2.5 p-2.5 rounded-lg border border-amber-300 dark:border-amber-700 bg-amber-50/70 dark:bg-amber-950/40 text-xs space-y-1">
                        <div className="flex items-center gap-1.5 text-amber-900 dark:text-amber-300 font-bold">
                          <span>⏸</span>
                          <span>{step.humanIntervention.title}</span>
                        </div>
                        <p className="text-amber-800 dark:text-amber-400 text-[11px]">
                          {step.humanIntervention.reason}
                        </p>
                        <p className="text-amber-700 dark:text-amber-300 text-[11px] font-medium italic">
                          Action Required: {step.humanIntervention.action_required}
                        </p>
                      </div>
                    )}

                    {/* Step Failed Error Callout */}
                    {step.status === "failed" && step.errorMessage && (
                      <div className="mt-2.5 p-2.5 rounded-lg border border-rose-300 dark:border-rose-800 bg-rose-50/70 dark:bg-rose-950/40 text-xs text-rose-700 dark:text-rose-300 font-medium">
                        <span className="font-bold">Error:</span> {step.errorMessage}
                      </div>
                    )}

                    {/* Step Skipped Explanation */}
                    {step.status === "skipped" && (
                      <p className="text-[11px] text-[#94A3B8] italic mt-1">
                        Step was not executed because upstream execution stopped.
                      </p>
                    )}

                    {isSelected && (
                      <div className="mt-3 pt-2.5 border-t border-[#E2E8F0] dark:border-[#1E293B] text-[11px] space-y-1.5 font-mono text-[#475569] dark:text-[#94A3B8]">
                        <div>Action: <strong className="text-[#0F172A] dark:text-[#F8FAFC]">{step.action}</strong></div>
                        {step.parameters && (
                          <div className="bg-[#F8FAFC] dark:bg-[#0B0F17] p-2 rounded border border-[#E2E8F0] dark:border-[#1E293B] overflow-x-auto">
                            {JSON.stringify(step.parameters, null, 2)}
                          </div>
                        )}
                        {step.errorMessage && (
                          <div className="text-rose-600 dark:text-rose-400 font-sans font-semibold">
                            Error: {step.errorMessage}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          // ================= HORIZONTAL CONNECTED PIPELINE (DEFAULT) =================
          <div className="min-w-max pb-2">
            <div className="grid grid-cols-6 gap-3 items-stretch relative">
              {derivedSteps.map((step, idx) => {
                const isSelected = selectedStepId === step.id;
                const isLast = idx === derivedSteps.length - 1;
                const appStyles = getAppBadgeClasses(step.application);
                const statusCfg = getStepStatusBadge(step.status);

                return (
                  <div key={step.id} className="relative flex flex-col justify-between">
                    {/* Node Card */}
                    <div
                      tabIndex={0}
                      role="button"
                      aria-label={`Step ${idx + 1}: ${step.name}. Status: ${statusCfg.label}. Click for details.`}
                      aria-expanded={isSelected}
                      onClick={() => setSelectedStepId(isSelected ? null : step.id)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          setSelectedStepId(isSelected ? null : step.id);
                        }
                      }}
                      className={`h-full p-3.5 rounded-xl border flex flex-col justify-between transition-all duration-150 cursor-pointer select-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${
                        isSelected
                          ? "border-[#2563EB] dark:border-[#3B82F6] ring-2 ring-[#2563EB]/25 bg-blue-50/20 dark:bg-blue-950/30 shadow-xs"
                          : step.status === "running"
                          ? "border-blue-400 dark:border-blue-500 bg-blue-50/25 dark:bg-blue-950/25 animate-node-pulse"
                          : step.status === "completed"
                          ? "border-emerald-200 dark:border-emerald-800/60 bg-emerald-50/20 dark:bg-emerald-950/20"
                          : step.status === "failed"
                          ? "border-rose-300 dark:border-rose-800 bg-rose-50/30 dark:bg-rose-950/20"
                          : step.status === "paused"
                          ? "border-amber-300 dark:border-amber-700 bg-amber-50/30 dark:bg-amber-950/20"
                          : step.status === "cancelled"
                          ? "border-slate-300 dark:border-slate-700 bg-slate-50/40 dark:bg-slate-900/40 opacity-80"
                          : step.status === "skipped"
                          ? "border-dashed border-slate-300 dark:border-slate-700 bg-slate-50/30 dark:bg-slate-900/30 opacity-70"
                          : "border-[#E2E8F0] dark:border-[#1E293B] hover:border-[#CBD5E1] dark:hover:border-[#334155] bg-white dark:bg-[#162035]"
                      }`}
                    >
                      {/* Step Header */}
                      <div>
                        <div className="flex items-center justify-between gap-1.5 mb-2">
                          {/* Step Index & App Badge */}
                          <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-md border flex items-center gap-1 ${appStyles.badge}`}>
                            <ApplicationIcon app={step.application} />
                            {getApplicationDisplayName(step.application)}
                          </span>

                          {/* Status Badge */}
                          <div
                            className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold shrink-0 transition-transform ${
                              step.status === "completed"
                                ? "bg-emerald-500 text-white"
                                : step.status === "running"
                                ? "bg-blue-600 text-white animate-spin"
                                : step.status === "failed"
                                ? "bg-rose-600 text-white"
                                : step.status === "paused"
                                ? "bg-amber-500 text-white"
                                : step.status === "cancelled"
                                ? "bg-slate-500 text-white"
                                : step.status === "skipped"
                                ? "bg-slate-300 dark:bg-slate-700 text-slate-600 dark:text-slate-300"
                                : "bg-slate-100 dark:bg-[#1E293B] text-slate-500 dark:text-slate-400 border border-[#E2E8F0] dark:border-slate-700"
                            }`}
                          >
                            {statusCfg.icon || idx + 1}
                          </div>
                        </div>

                        {/* Step Title */}
                        <div className="text-xs font-bold text-[#0F172A] dark:text-[#F8FAFC] leading-snug line-clamp-2">
                          {step.name}
                        </div>

                        {/* Action Code Tag & Duration if available */}
                        <div className="mt-1 flex items-center justify-between gap-1 text-[10px] font-mono text-[#64748B] dark:text-[#94A3B8]">
                          <span className="truncate">{step.action}</span>
                          {typeof step.durationSeconds === "number" && (
                            <span className="shrink-0">{step.durationSeconds.toFixed(2)}s</span>
                          )}
                        </div>
                      </div>

                      {/* Footer & Expand Hint */}
                      <div className="mt-3 pt-2 border-t border-[#F1F5F9] dark:border-[#1E293B] flex items-center justify-between text-[10px]">
                        <span
                          className={`font-semibold capitalize ${
                            step.status === "completed"
                              ? "text-emerald-700 dark:text-emerald-400"
                              : step.status === "running"
                              ? "text-blue-700 dark:text-blue-400"
                              : step.status === "failed"
                              ? "text-rose-700 dark:text-rose-400"
                              : step.status === "paused"
                              ? "text-amber-700 dark:text-amber-400"
                              : step.status === "cancelled"
                              ? "text-slate-600 dark:text-slate-400"
                              : step.status === "skipped"
                              ? "text-slate-500 dark:text-slate-400"
                              : "text-[#94A3B8]"
                          }`}
                        >
                          {statusCfg.label}
                        </span>
                        <span className="text-[#94A3B8] font-mono hover:text-[#2563EB] dark:hover:text-[#60A5FA]">
                          {isSelected ? "▲ Less" : "▼ Info"}
                        </span>
                      </div>
                    </div>

                    {/* Animated Flow Connector Arrow to Next Node */}
                    {!isLast && (
                      <div
                        className="hidden lg:block absolute -right-3 top-1/2 -translate-y-1/2 z-20 pointer-events-none"
                        aria-hidden="true"
                      >
                        <div
                          className={`w-3.5 h-0.5 rounded-full ${
                            step.status === "completed" && derivedSteps[idx + 1]?.status === "running"
                              ? "animate-connector-flow h-1"
                              : step.status === "completed"
                              ? "bg-emerald-400 dark:bg-emerald-600"
                              : "bg-slate-300 dark:bg-slate-700"
                          }`}
                        />
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {/* Expandable Parameter Inspector Drawer for the selected step */}
            {selectedStepId && (
              <div className="mt-4 p-4 rounded-xl border border-[#E2E8F0] dark:border-[#1E293B] bg-[#F8FAFC] dark:bg-[#0B0F17] animate-card-enter space-y-2">
                {(() => {
                  const step = derivedSteps.find((s) => s.id === selectedStepId);
                  if (!step) return null;
                  return (
                    <div>
                      <div className="flex items-center justify-between pb-2 border-b border-[#E2E8F0] dark:border-[#1E293B]">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-bold text-[#0F172A] dark:text-[#F8FAFC]">
                            {step.name} ({step.action})
                          </span>
                          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-200 dark:bg-[#1E293B] text-slate-700 dark:text-slate-300">
                            {step.id}
                          </span>
                        </div>
                        <button
                          type="button"
                          onClick={() => setSelectedStepId(null)}
                          className="text-xs text-[#64748B] hover:text-[#0F172A] dark:hover:text-white cursor-pointer"
                        >
                          ✕ Close Inspector
                        </button>
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2 text-xs">
                        <div>
                          <span className="text-[10px] font-semibold text-[#64748B] dark:text-[#94A3B8] uppercase block">
                            Description
                          </span>
                          <p className="text-xs text-[#0F172A] dark:text-[#F8FAFC] mt-0.5">
                            {step.description || "No description provided."}
                          </p>

                          {step.retryAttempts !== undefined && (
                            <div className="mt-2 text-[11px] text-[#64748B] dark:text-[#94A3B8]">
                              Retry Policy: <strong className="text-[#0F172A] dark:text-[#F8FAFC]">{step.retryAttempts} max attempts</strong>
                            </div>
                          )}
                        </div>

                        <div>
                          <span className="text-[10px] font-semibold text-[#64748B] dark:text-[#94A3B8] uppercase block">
                            Parameters & Template Inputs
                          </span>
                          {step.parameters ? (
                            <pre className="mt-1 p-2 rounded bg-white dark:bg-[#162035] border border-[#E2E8F0] dark:border-[#1E293B] text-[11px] font-mono text-[#0F172A] dark:text-[#F8FAFC] overflow-x-auto">
                              {JSON.stringify(step.parameters, null, 2)}
                            </pre>
                          ) : (
                            <p className="text-[11px] text-[#94A3B8] italic mt-1">No custom parameters</p>
                          )}
                        </div>
                      </div>

                      {typeof step.durationSeconds === "number" && (
                        <div className="mt-2 text-[11px] text-[#64748B] dark:text-[#94A3B8]">
                          Duration: <strong className="text-[#0F172A] dark:text-[#F8FAFC]">{step.durationSeconds.toFixed(2)}s</strong>
                        </div>
                      )}

                      {step.timestamp && (
                        <div className="mt-1 text-[11px] text-[#64748B] dark:text-[#94A3B8]">
                          Executed at: <strong className="text-[#0F172A] dark:text-[#F8FAFC]">{new Date(step.timestamp).toLocaleTimeString()}</strong>
                        </div>
                      )}

                      {step.humanIntervention && (
                        <div className="mt-2 p-2.5 rounded bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 text-xs space-y-1">
                          <p className="font-bold text-amber-900 dark:text-amber-300">
                            ⏸ {step.humanIntervention.title}
                          </p>
                          <p className="text-amber-800 dark:text-amber-400">
                            {step.humanIntervention.reason}
                          </p>
                          <p className="text-amber-700 dark:text-amber-300 italic font-medium">
                            Action required: {step.humanIntervention.action_required}
                          </p>
                        </div>
                      )}

                      {step.errorMessage && (
                        <div className="mt-2 p-2.5 rounded bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-xs text-rose-700 dark:text-rose-300 font-medium">
                          Failed Reason: {step.errorMessage}
                        </div>
                      )}
                    </div>
                  );
                })()}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
