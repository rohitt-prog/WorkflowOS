"use client";

import React, { useState, useEffect } from "react";
import { createPortal } from "react-dom";
import { AutomationExecutionRecord, ActionDetail } from "@/lib/types";
import { statusBadgeConfig, getApplicationDisplayName, getAppBadgeClass, API_BASE_URL, formatApiErrorMessage } from "@/lib/utils";
import WorkflowVisualizer from "@/components/WorkflowVisualizer";
import ExecutionSummary from "@/components/ExecutionSummary";

interface ExecutionsViewProps {
  executions: AutomationExecutionRecord[];
  loading: boolean;
  onRefresh: () => void;
}

export function ExecutionDetailModal({
  execution,
  onClose,
  onRefresh,
}: {
  execution: AutomationExecutionRecord;
  onClose: () => void;
  onRefresh?: () => void;
}) {
  const [isResuming, setIsResuming] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState(false);

  // Lock body scroll while modal is open to avoid background page shifting
  useEffect(() => {
    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = originalOverflow;
    };
  }, []);

  // Keyboard accessibility: Escape to close modal
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !isResuming && !isCancelling) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose, isResuming, isCancelling]);

  const handleCopyId = async (e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      if (typeof navigator !== "undefined" && navigator.clipboard) {
        await navigator.clipboard.writeText(execution.execution_id);
        setCopiedId(true);
        setTimeout(() => setCopiedId(false), 2000);
      }
    } catch {
      // Fallback
    }
  };

  const handleResume = async () => {
    setIsResuming(true);
    setActionError(null);
    try {
      const res = await fetch(
        `${API_BASE_URL}/api/automation/executions/${execution.execution_id}/resume`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ executor_type: "playwright" }),
        }
      );
      if (!res.ok) {
        const err = await res.json().catch(() => null);
        throw new Error(formatApiErrorMessage(err, `Resume failed (${res.status})`));
      }
      onRefresh?.();
      onClose();
    } catch (e: unknown) {
      setActionError(e instanceof Error ? e.message : "Resume failed");
    } finally {
      setIsResuming(false);
    }
  };

  const handleCancel = async () => {
    setIsCancelling(true);
    setActionError(null);
    try {
      const res = await fetch(
        `${API_BASE_URL}/api/automation/executions/${execution.execution_id}/cancel`,
        { method: "POST" }
      );
      if (!res.ok) {
        const err = await res.json().catch(() => null);
        throw new Error(formatApiErrorMessage(err, `Cancel failed (${res.status})`));
      }
      onRefresh?.();
      onClose();
    } catch (e: unknown) {
      setActionError(e instanceof Error ? e.message : "Cancel failed");
    } finally {
      setIsCancelling(false);
    }
  };

  const cfg = statusBadgeConfig(execution.status);
  const actions: ActionDetail[] = execution.all_actions || execution.actions_detail || [];

  if (typeof document === "undefined") {
    return null;
  }

  const modalOverlay = (
    <div
      className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4 sm:p-6 z-50 overflow-hidden overscroll-contain animate-fadeIn"
      onClick={onClose}
    >
      <div
        className="bg-white border border-[#E2E8F0] rounded-2xl max-w-3xl w-full shadow-2xl flex flex-col max-h-[calc(100dvh-32px)] sm:max-h-[calc(100dvh-48px)] overflow-hidden animate-modal-enter"
        onClick={(e) => e.stopPropagation()}
      >
        {/* HEADER: fixed/sticky inside modal */}
        <div className="px-6 py-4.5 border-b border-[#E2E8F0] dark:border-[#1E293B] flex items-start justify-between shrink-0 bg-[#F8FAFC] dark:bg-[#0B0F17]">
          <div>
            <div className="flex items-center gap-2 mb-1 flex-wrap">
              <span className={`text-xs font-semibold px-2 py-0.5 rounded-full border ${cfg.className}`}>
                {cfg.label}
              </span>
              <div className="flex items-center gap-1">
                <code className="text-[11px] font-mono text-[#64748B] dark:text-[#94A3B8] bg-white dark:bg-[#162035] px-2 py-0.5 rounded border border-[#E2E8F0] dark:border-[#1E293B]">
                  {execution.execution_id}
                </code>
                <button
                  type="button"
                  onClick={handleCopyId}
                  className="p-1 rounded text-[#64748B] hover:text-[#0F172A] dark:text-[#94A3B8] dark:hover:text-white hover:bg-slate-200 dark:hover:bg-[#1E293B] transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
                  title="Copy execution ID"
                  aria-label="Copy execution ID"
                >
                  {copiedId ? (
                    <span className="text-[10px] text-emerald-600 dark:text-emerald-400 font-semibold">✓</span>
                  ) : (
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                    </svg>
                  )}
                </button>
              </div>
            </div>
            <h3 className="text-base font-bold text-[#0F172A] dark:text-[#F8FAFC]">
              {execution.workflow_name || "Automation Workflow"}
            </h3>
          </div>
          <button
            onClick={onClose}
            className="text-[#94A3B8] hover:text-[#0F172A] dark:hover:text-white p-1.5 rounded-lg hover:bg-[#E2E8F0] dark:hover:bg-[#1E293B] transition-colors duration-150 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
            aria-label="Close execution details"
          >
            ✕
          </button>
        </div>

        {/* CONTENT: ONLY this region scrolls */}
        <div className="flex-1 min-h-0 overflow-y-auto px-6 py-5 space-y-5 text-xs overscroll-contain">
          {/* Polished Compact Execution Summary */}
          <ExecutionSummary execution={execution} isExecuting={false} />

          {/* Visual Execution Pipeline & Timeline Status */}
          <WorkflowVisualizer
            execution={execution}
            workflowName={execution.workflow_name}
          />

          {/* Steps Audit Trail */}
          <div className="bg-white dark:bg-[#111827] border border-[#E2E8F0] dark:border-[#1E293B] rounded-2xl p-4 shadow-2xs space-y-3">
            <div className="flex items-center justify-between">
              <h4 className="font-semibold text-[#0F172A] dark:text-[#F8FAFC] uppercase tracking-wider text-[11px]">
                Action Execution Trace ({actions.length} records)
              </h4>
              <span className="text-[10px] text-[#64748B] dark:text-[#94A3B8] font-mono">
                Chronological Log
              </span>
            </div>

            {actions.length === 0 ? (
              <p className="text-xs text-[#94A3B8] italic py-2">No step records available.</p>
            ) : (
              <div className="space-y-2">
                {actions.map((act, idx) => (
                  <div
                    key={act.action_id || idx}
                    className="flex items-start gap-3 p-3 rounded-xl border border-[#E2E8F0] dark:border-[#1E293B] bg-[#F8FAFC] dark:bg-[#162035] transition-colors"
                  >
                    <span
                      className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold shrink-0 mt-0.5 ${
                        act.status === "completed"
                          ? "bg-[#16A34A] text-white"
                          : act.status === "failed"
                          ? "bg-[#DC2626] text-white"
                          : act.status === "running"
                          ? "bg-[#2563EB] text-white animate-spin"
                          : "bg-slate-200 dark:bg-slate-700 text-slate-500 dark:text-slate-400"
                      }`}
                    >
                      {act.status === "completed" ? "✓" : act.status === "failed" ? "✕" : "○"}
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-2 flex-wrap">
                        <span className="font-mono font-semibold text-xs text-[#0F172A] dark:text-[#F8FAFC]">
                          {act.action || act.action_type || `Action #${idx + 1}`}
                        </span>
                        <div className="flex items-center gap-1.5 shrink-0">
                          {act.application && (
                            <span className={`text-[10px] font-medium px-2 py-0.5 rounded border shrink-0 ${getAppBadgeClass(act.application)}`}>
                              {getApplicationDisplayName(act.application)}
                            </span>
                          )}
                          <span
                            className={`text-[10px] font-semibold px-1.5 py-0.5 rounded capitalize ${
                              act.status === "completed"
                                ? "bg-emerald-100 dark:bg-emerald-950/40 text-emerald-800 dark:text-emerald-300"
                                : act.status === "failed"
                                ? "bg-rose-100 dark:bg-rose-950/40 text-rose-800 dark:text-rose-300"
                                : "bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300"
                            }`}
                          >
                            {act.status}
                          </span>
                        </div>
                      </div>
                      {act.message && (
                        <p className="text-[11px] text-[#64748B] dark:text-[#94A3B8] mt-1 break-words">
                          {act.message}
                        </p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* FOOTER: fixed/sticky inside modal */}
        <div className="px-6 py-4 border-t border-[#E2E8F0] bg-[#F8FAFC] flex items-center justify-between shrink-0">
          <div>
            {actionError && (
              <span className="text-xs text-rose-600 font-medium">{actionError}</span>
            )}
          </div>
          <div className="flex items-center gap-2.5">
            {execution.status === "paused" && execution.resume_available && (
              <>
                <button
                  onClick={handleCancel}
                  disabled={isCancelling || isResuming}
                  className="px-3.5 py-2 text-xs font-semibold rounded-lg bg-white hover:bg-rose-50 text-[#DC2626] border border-rose-200 transition-colors duration-150 active:translate-y-px disabled:opacity-60 cursor-pointer"
                >
                  {isCancelling ? "Cancelling…" : "Cancel Execution"}
                </button>
                <button
                  onClick={handleResume}
                  disabled={isCancelling || isResuming}
                  className="px-4 py-2 text-xs font-semibold rounded-lg bg-[#2563EB] hover:bg-[#1D4ED8] text-white shadow-2xs transition-colors duration-150 active:translate-y-px disabled:opacity-60 cursor-pointer"
                >
                  {isResuming ? "Resuming…" : "Resume Execution"}
                </button>
              </>
            )}
            {execution.status !== "paused" && (
              <button
                onClick={onClose}
                className="px-4 py-2 text-xs font-medium rounded-lg bg-white hover:bg-[#F8FAFC] border border-[#E2E8F0] text-[#0F172A] shadow-2xs transition-colors duration-150 active:translate-y-px cursor-pointer"
              >
                Close
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );

  return createPortal(modalOverlay, document.body);
}

export default function ExecutionsView({
  executions,
  loading,
  onRefresh,
}: ExecutionsViewProps) {
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [selectedExecution, setSelectedExecution] = useState<AutomationExecutionRecord | null>(null);

  const statuses = ["ALL", "completed", "running", "paused", "failed", "cancelled"];

  const filteredExecutions = executions.filter((e) => {
    if (statusFilter === "ALL") return true;
    return e.status === statusFilter;
  });

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6 bg-[#F7F9FC]">
      {/* Header bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white border border-[#E2E8F0] rounded-xl p-5 shadow-2xs">
        <div>
          <h2 className="text-lg font-bold text-[#0F172A] tracking-tight">
            Execution Telemetry & Audit Logs
          </h2>
          <p className="text-xs text-[#64748B] mt-0.5">
            History of automated workflow runs, step logs, human-in-the-loop pause states, and resume control.
          </p>
        </div>
        <button
          onClick={onRefresh}
          className="flex items-center gap-2 px-3.5 py-2 text-xs font-semibold rounded-lg bg-white hover:bg-[#F8FAFC] border border-[#E2E8F0] text-[#0F172A] shadow-2xs transition-all duration-150 active:translate-y-px cursor-pointer self-start sm:self-auto"
        >
          <svg className="w-3.5 h-3.5 text-[#475569]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          <span>Refresh Executions</span>
        </button>
      </div>

      {/* Status Filter Tabs */}
      <div className="flex items-center gap-1.5 overflow-x-auto pb-1 scrollbar-hide">
        {statuses.map((s) => {
          const count =
            s === "ALL"
              ? executions.length
              : executions.filter((e) => e.status === s).length;
          if (count === 0 && s !== "ALL") return null;
          return (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition cursor-pointer border ${
                statusFilter === s
                  ? "bg-[#DBEAFE] border-[#BFDBFE] text-[#1D4ED8] font-semibold"
                  : "bg-white border-[#E2E8F0] text-[#64748B] hover:text-[#0F172A] hover:bg-[#F8FAFC]"
              }`}
            >
              <span className="capitalize">{s}</span>
              <span
                className={`text-[10px] font-mono px-1.5 py-0.2 rounded-full border ${
                  statusFilter === s
                    ? "bg-white border-[#BFDBFE] text-[#1D4ED8]"
                    : "bg-[#F1F5F9] border-[#E2E8F0] text-[#64748B]"
                }`}
              >
                {count}
              </span>
            </button>
          );
        })}
      </div>

      {/* Executions Table / Cards */}
      <div className="bg-white border border-[#E2E8F0] rounded-xl overflow-hidden shadow-2xs">
        {loading ? (
          <div className="p-6 space-y-4">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="flex items-center gap-4 animate-pulse">
                <div className="h-6 w-20 bg-[#F1F5F9] rounded" />
                <div className="h-4 flex-1 bg-[#F1F5F9] rounded" />
                <div className="h-4 w-28 bg-[#F1F5F9] rounded" />
              </div>
            ))}
          </div>
        ) : filteredExecutions.length === 0 ? (
          <div className="py-16 text-center px-4">
            <div className="w-12 h-12 rounded-xl bg-[#F1F5F9] text-[#94A3B8] flex items-center justify-center mx-auto mb-3">
              <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
              </svg>
            </div>
            <h3 className="text-sm font-semibold text-[#0F172A]">No execution logs found</h3>
            <p className="text-xs text-[#64748B] mt-1">
              Trigger a workflow execution via the Discovery view or Workflow Builder.
            </p>
          </div>
        ) : (
          <table className="w-full text-left text-xs border-collapse">
            <thead className="bg-[#F8FAFC] text-[#64748B] font-semibold border-b border-[#E2E8F0]">
              <tr>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">Workflow Name</th>
                <th className="py-3 px-4">Execution ID</th>
                <th className="py-3 px-4">Progress</th>
                <th className="py-3 px-4">Duration</th>
                <th className="py-3 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E2E8F0]">
              {filteredExecutions.map((exec) => {
                const cfg = statusBadgeConfig(exec.status);
                const progress =
                  exec.total_actions > 0
                    ? Math.round((exec.completed_actions.length / exec.total_actions) * 100)
                    : 0;

                return (
                  <tr
                    key={exec.execution_id}
                    tabIndex={0}
                    role="button"
                    aria-label={`Inspect execution ${exec.execution_id} for ${exec.workflow_name || "Automation Workflow"}`}
                    onClick={() => setSelectedExecution(exec)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        setSelectedExecution(exec);
                      }
                    }}
                    className="hover:bg-[#F8FAFC] transition-colors duration-150 animate-row-enter cursor-pointer group focus-visible:outline-none focus-visible:bg-[#F1F5F9]"
                  >
                    <td className="py-3 px-4 whitespace-nowrap">
                      <span className={`inline-flex items-center gap-1.5 text-[10px] font-semibold px-2 py-0.5 rounded-full border ${cfg.className}`}>
                        {cfg.dot && <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />}
                        <span>{cfg.label}</span>
                      </span>
                    </td>
                    <td className="py-3 px-4 font-semibold text-[#0F172A] whitespace-nowrap">
                      {exec.workflow_name || "Automation Workflow"}
                    </td>
                    <td className="py-3 px-4 font-mono text-[#64748B] text-[11px] whitespace-nowrap">
                      <span title={exec.execution_id}>
                        {exec.execution_id.length > 20
                          ? `${exec.execution_id.slice(0, 8)}…${exec.execution_id.slice(-6)}`
                          : exec.execution_id}
                      </span>
                    </td>
                    <td className="py-3 px-4 whitespace-nowrap">
                      <div className="flex items-center gap-2">
                        <div className="w-20 h-1.5 bg-[#F1F5F9] rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full ${
                              exec.status === "completed"
                                ? "bg-[#16A34A]"
                                : exec.status === "failed"
                                ? "bg-[#DC2626]"
                                : exec.status === "paused"
                                ? "bg-[#F59E0B]"
                                : "bg-[#2563EB]"
                            }`}
                            style={{ width: `${progress}%` }}
                          />
                        </div>
                        <span className="text-[11px] text-[#64748B] font-mono">
                          {exec.completed_actions.length}/{exec.total_actions}
                        </span>
                      </div>
                    </td>
                    <td className="py-3 px-4 font-mono text-[#64748B] text-[11px] whitespace-nowrap">
                      {exec.execution_time_seconds != null ? `${exec.execution_time_seconds}s` : "—"}
                    </td>
                    <td className="py-3 px-4 text-right whitespace-nowrap">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedExecution(exec);
                        }}
                        className="px-2.5 py-1 text-xs font-semibold rounded bg-white hover:bg-[#F8FAFC] border border-[#E2E8F0] text-[#2563EB] shadow-2xs transition-all duration-150 active:translate-y-px cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
                      >
                        Inspect →
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Detail Modal */}
      {selectedExecution && (
        <ExecutionDetailModal
          execution={selectedExecution}
          onClose={() => setSelectedExecution(null)}
          onRefresh={onRefresh}
        />
      )}
    </div>
  );
}
