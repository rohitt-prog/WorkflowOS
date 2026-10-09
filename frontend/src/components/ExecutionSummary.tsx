"use client";

import React, { useState } from "react";
import {
  AutomationExecutionResponse,
  AutomationExecutionRecord,
} from "@/lib/types";
import { statusBadgeConfig } from "@/lib/utils";

export interface ExecutionSummaryProps {
  execution: AutomationExecutionResponse | AutomationExecutionRecord;
  workflowName?: string;
  isExecuting?: boolean;
  className?: string;
  compact?: boolean;
}

/**
 * Compact, restrained execution summary displaying only real available data.
 * Adheres to dark/light theme tokens and accessibility standards.
 */
export default function ExecutionSummary({
  execution,
  workflowName,
  isExecuting = false,
  className = "",
  compact = false,
}: ExecutionSummaryProps) {
  const [copied, setCopied] = useState(false);

  const status = isExecuting ? "running" : execution.status || "pending";
  const cfg = statusBadgeConfig(status);

  const name =
    execution.workflow_name ||
    workflowName ||
    ("workflow_id" in execution ? execution.workflow_id : "Automation Workflow");

  const execId =
    "execution_id" in execution && execution.execution_id
      ? execution.execution_id
      : "workflow_id" in execution && execution.workflow_id
      ? execution.workflow_id
      : undefined;

  const completedCount = execution.completed_actions?.length ?? 0;
  const totalCount = execution.total_actions ?? 0;
  const progressPercent =
    totalCount > 0 ? Math.min(100, Math.round((completedCount / totalCount) * 100)) : 0;

  const durationSeconds =
    typeof execution.execution_time_seconds === "number" &&
    !Number.isNaN(execution.execution_time_seconds)
      ? execution.execution_time_seconds
      : null;

  const failureReason =
    execution.failure_reason ||
    ("error" in execution && typeof execution.error === "string" ? execution.error : null) ||
    ("message" in execution && typeof execution.message === "string" && status === "failed"
      ? execution.message
      : null);

  const failedAction = execution.failed_action;

  const humanIntervention =
    "human_intervention" in execution ? execution.human_intervention : undefined;

  const handleCopyId = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!execId) return;
    try {
      if (typeof navigator !== "undefined" && navigator.clipboard) {
        await navigator.clipboard.writeText(execId);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      }
    } catch {
      // Fallback
    }
  };

  const formatIsoTime = (iso?: string | null) => {
    if (!iso) return null;
    try {
      const d = new Date(iso);
      if (Number.isNaN(d.getTime())) return null;
      return d.toLocaleTimeString(undefined, {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      });
    } catch {
      return null;
    }
  };

  const startedTime = formatIsoTime(execution.started_at);
  const completedTime = formatIsoTime(execution.completed_at);
  const pausedTime = formatIsoTime(execution.paused_at);

  return (
    <div
      className={`rounded-2xl border transition-colors duration-150 ${
        status === "completed"
          ? "bg-emerald-50/40 dark:bg-emerald-950/20 border-emerald-200 dark:border-emerald-800/60"
          : status === "failed"
          ? "bg-rose-50/40 dark:bg-rose-950/20 border-rose-200 dark:border-rose-800/60"
          : status === "paused"
          ? "bg-amber-50/40 dark:bg-amber-950/20 border-amber-200 dark:border-amber-800/60"
          : status === "cancelled"
          ? "bg-slate-50/50 dark:bg-slate-900/40 border-slate-200 dark:border-slate-800"
          : "bg-white dark:bg-[#111827] border-[#E2E8F0] dark:border-[#1E293B]"
      } ${compact ? "p-3.5" : "p-4 sm:p-5"} ${className}`}
      role="region"
      aria-label="Workflow Execution Summary"
    >
      {/* Top Banner: Status, Workflow Name & Copy ID */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-2.5 min-w-0">
          <span
            className={`inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full border shrink-0 transition-colors ${cfg.className}`}
          >
            {cfg.dot && <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />}
            <span>{isExecuting ? "Executing…" : cfg.label}</span>
          </span>

          <h3 className="text-sm sm:text-base font-bold text-[#0F172A] dark:text-[#F8FAFC] truncate">
            {name}
          </h3>
        </div>

        {execId && (
          <div className="flex items-center gap-1.5 self-start sm:self-auto shrink-0">
            <code
              className="text-[11px] font-mono px-2 py-0.5 rounded border bg-white dark:bg-[#162035] border-[#E2E8F0] dark:border-[#1E293B] text-[#64748B] dark:text-[#94A3B8]"
              title={execId}
            >
              {execId.length > 24 ? `${execId.slice(0, 10)}…${execId.slice(-8)}` : execId}
            </code>
            <button
              type="button"
              onClick={handleCopyId}
              className="p-1 rounded-md text-[#64748B] hover:text-[#0F172A] dark:text-[#94A3B8] dark:hover:text-[#F8FAFC] hover:bg-slate-100 dark:hover:bg-[#1E293B] transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
              title="Copy Execution ID"
              aria-label="Copy Execution ID to clipboard"
            >
              {copied ? (
                <span className="text-[10px] font-medium text-emerald-600 dark:text-emerald-400 flex items-center gap-0.5">
                  <svg className="w-3.5 h-3.5" viewBox="0 0 20 20" fill="currentColor">
                    <path
                      fillRule="evenodd"
                      d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                      clipRule="evenodd"
                    />
                  </svg>
                  Copied
                </span>
              ) : (
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
                  />
                </svg>
              )}
            </button>
          </div>
        )}
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 mt-3.5 text-xs">
        {/* Step Progress */}
        <div className="bg-white/80 dark:bg-[#162035]/80 border border-[#E2E8F0] dark:border-[#1E293B] rounded-xl p-2.5">
          <span className="text-[10px] font-medium text-[#64748B] dark:text-[#94A3B8] block uppercase tracking-wider">
            Step Progress
          </span>
          <div className="flex items-baseline gap-1 mt-0.5">
            <span className="text-sm font-bold font-mono text-[#0F172A] dark:text-[#F8FAFC]">
              {completedCount}
            </span>
            <span className="text-xs text-[#64748B] dark:text-[#94A3B8] font-mono">
              / {totalCount} completed
            </span>
          </div>
          <div className="w-full bg-slate-200 dark:bg-slate-700 h-1 rounded-full mt-2 overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-300 ${
                status === "completed"
                  ? "bg-emerald-500"
                  : status === "failed"
                  ? "bg-rose-500"
                  : status === "paused"
                  ? "bg-amber-500"
                  : "bg-blue-600"
              }`}
              style={{ width: `${progressPercent}%` }}
            />
          </div>
        </div>

        {/* Duration (only when available) */}
        <div className="bg-white/80 dark:bg-[#162035]/80 border border-[#E2E8F0] dark:border-[#1E293B] rounded-xl p-2.5">
          <span className="text-[10px] font-medium text-[#64748B] dark:text-[#94A3B8] block uppercase tracking-wider">
            Duration
          </span>
          <div className="text-sm font-bold font-mono text-[#0F172A] dark:text-[#F8FAFC] mt-0.5">
            {durationSeconds !== null ? `${durationSeconds.toFixed(2)}s` : "—"}
          </div>
          <span className="text-[10px] text-[#64748B] dark:text-[#94A3B8] block mt-1">
            {durationSeconds !== null ? "Total execution time" : "In progress or pending"}
          </span>
        </div>

        {/* Started Time */}
        <div className="bg-white/80 dark:bg-[#162035]/80 border border-[#E2E8F0] dark:border-[#1E293B] rounded-xl p-2.5">
          <span className="text-[10px] font-medium text-[#64748B] dark:text-[#94A3B8] block uppercase tracking-wider">
            Started At
          </span>
          <div className="text-xs font-mono font-semibold text-[#0F172A] dark:text-[#F8FAFC] mt-0.5">
            {startedTime || "—"}
          </div>
          <span className="text-[10px] text-[#64748B] dark:text-[#94A3B8] block mt-1">
            {completedTime ? `Ended: ${completedTime}` : pausedTime ? `Paused: ${pausedTime}` : "Start timestamp"}
          </span>
        </div>

        {/* Resumes or Outcome */}
        <div className="bg-white/80 dark:bg-[#162035]/80 border border-[#E2E8F0] dark:border-[#1E293B] rounded-xl p-2.5">
          <span className="text-[10px] font-medium text-[#64748B] dark:text-[#94A3B8] block uppercase tracking-wider">
            Outcome Status
          </span>
          <div className="text-xs font-semibold capitalize text-[#0F172A] dark:text-[#F8FAFC] mt-0.5">
            {status}
          </div>
          <span className="text-[10px] text-[#64748B] dark:text-[#94A3B8] block mt-1">
            {(execution.resume_count ?? 0) > 0 ? `${execution.resume_count} resume cycles` : "Standard run"}
          </span>
        </div>
      </div>

      {/* Human Intervention Banner for Paused State */}
      {(status === "paused" || execution.requires_human_intervention) && (
        <div className="mt-3.5 p-3.5 rounded-xl border border-amber-300 dark:border-amber-700/70 bg-white/90 dark:bg-[#162035] space-y-1 text-xs">
          <div className="flex items-center gap-2 text-amber-900 dark:text-amber-300 font-bold">
            <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
            <span>
              {humanIntervention?.title || "⏸ Human Intervention Required"}
            </span>
          </div>
          {humanIntervention?.reason && (
            <p className="text-amber-800 dark:text-amber-400">
              {humanIntervention.reason}
            </p>
          )}
          {humanIntervention?.action_required && (
            <p className="text-amber-700 dark:text-amber-300/90 font-medium italic">
              Required: {humanIntervention.action_required}
            </p>
          )}
        </div>
      )}

      {/* Error Callout Banner for Failed State */}
      {status === "failed" && failureReason && (
        <div className="mt-3.5 p-3 rounded-xl border border-rose-300 dark:border-rose-800 bg-white/90 dark:bg-[#162035] text-xs space-y-1">
          <div className="flex items-center gap-1.5 text-rose-800 dark:text-rose-300 font-bold">
            <span>⚠</span>
            <span>Execution Blocked</span>
            {failedAction && (
              <span className="font-mono text-[11px] text-rose-700 dark:text-rose-400 font-normal">
                at step <strong>&ldquo;{failedAction}&rdquo;</strong>
              </span>
            )}
          </div>
          <p className="text-rose-700 dark:text-rose-400 break-words font-medium">
            {failureReason}
          </p>
        </div>
      )}
    </div>
  );
}
