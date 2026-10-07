"use client";

import React, { useState, useEffect } from "react";
import { createPortal } from "react-dom";
import { AutomationExecutionRecord, ActionDetail } from "@/lib/types";
import { statusBadgeConfig, getApplicationDisplayName, getAppBadgeClass, API_BASE_URL, formatApiErrorMessage } from "@/lib/utils";

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

  // Lock body scroll while modal is open to avoid background page shifting
  useEffect(() => {
    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = originalOverflow;
    };
  }, []);

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
  const progress =
    execution.total_actions > 0
      ? Math.round((execution.completed_actions.length / execution.total_actions) * 100)
      : 0;

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
        <div className="px-6 py-4.5 border-b border-[#E2E8F0] flex items-start justify-between shrink-0 bg-[#F8FAFC]">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className={`text-xs font-semibold px-2 py-0.5 rounded-full border ${cfg.className}`}>
                {cfg.label}
              </span>
              <code className="text-[11px] font-mono text-[#64748B] bg-white px-2 py-0.5 rounded border border-[#E2E8F0]">
                {execution.execution_id}
              </code>
            </div>
            <h3 className="text-base font-bold text-[#0F172A]">
              {execution.workflow_name || "Automation Workflow"}
            </h3>
          </div>
          <button
            onClick={onClose}
            className="text-[#94A3B8] hover:text-[#0F172A] p-1.5 rounded-lg hover:bg-[#E2E8F0] transition-colors duration-150 cursor-pointer"
            aria-label="Close execution details"
          >
            ✕
          </button>
        </div>

        {/* CONTENT: ONLY this region scrolls */}
        <div className="flex-1 min-h-0 overflow-y-auto px-6 py-5 space-y-5 text-xs overscroll-contain">
          {/* Metadata Cards */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg p-3">
              <span className="text-[10px] text-[#64748B] block font-medium">Progress</span>
              <span className="text-sm font-bold text-[#0F172A]">
                {execution.completed_actions.length} / {execution.total_actions}
              </span>
            </div>
            <div className="bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg p-3">
              <span className="text-[10px] text-[#64748B] block font-medium">Runtime</span>
              <span className="text-sm font-bold text-[#0F172A]">
                {execution.execution_time_seconds != null ? `${execution.execution_time_seconds}s` : "—"}
              </span>
            </div>
            <div className="bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg p-3">
              <span className="text-[10px] text-[#64748B] block font-medium">Started At</span>
              <span className="text-[11px] font-mono text-[#0F172A]">
                {execution.started_at ? new Date(execution.started_at).toLocaleTimeString() : "—"}
              </span>
            </div>
            <div className="bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg p-3">
              <span className="text-[10px] text-[#64748B] block font-medium">Resumes</span>
              <span className="text-sm font-bold text-[#0F172A]">
                {execution.resume_count ?? 0}
              </span>
            </div>
          </div>

          {/* Progress Bar */}
          <div>
            <div className="flex items-center justify-between text-[11px] text-[#64748B] mb-1">
              <span>Overall Completion</span>
              <span className="font-semibold text-[#0F172A]">{progress}%</span>
            </div>
            <div className="h-2 bg-[#F1F5F9] rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-300 ${
                  execution.status === "completed"
                    ? "bg-[#16A34A]"
                    : execution.status === "failed"
                    ? "bg-[#DC2626]"
                    : execution.status === "paused"
                    ? "bg-[#F59E0B]"
                    : "bg-[#2563EB]"
                }`}
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>

          {/* Action Required Banner for Paused executions */}
          {execution.status === "paused" && (
            <div className="bg-amber-50 border border-amber-300 rounded-xl p-4 text-xs space-y-1">
              <div className="flex items-center gap-2 text-amber-900 font-bold">
                <span>⏸ Operator Action Required</span>
              </div>
              <p className="text-amber-800">
                Action <code className="font-mono bg-amber-100 px-1 py-0.5 rounded text-amber-900">{execution.current_action || "current"}</code> paused due to missing target or validation condition.
              </p>
              {execution.error && (
                <p className="text-amber-700 italic mt-1 font-mono text-[11px]">
                  Reason: {execution.error}
                </p>
              )}
            </div>
          )}

          {/* Error Banner */}
          {execution.error && execution.status !== "paused" && (
            <div className="bg-rose-50 border border-rose-200 rounded-xl p-3.5 text-xs text-rose-700">
              <span className="font-semibold">Execution Failure: </span>
              {execution.error}
            </div>
          )}

          {/* Steps Audit Trail */}
          <div>
            <h4 className="font-semibold text-[#0F172A] uppercase tracking-wider text-[11px] mb-2.5">
              Action Execution Trace
            </h4>
            {actions.length === 0 ? (
              <p className="text-xs text-[#94A3B8] italic">No step records available.</p>
            ) : (
              <div className="space-y-2">
                {actions.map((act, idx) => (
                  <div
                    key={act.action_id || idx}
                    className="flex items-start gap-3 p-3 rounded-xl border border-[#E2E8F0] bg-white shadow-2xs"
                  >
                    <span
                      className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold shrink-0 mt-0.5 ${
                        act.status === "completed"
                          ? "bg-[#16A34A] text-white"
                          : act.status === "failed"
                          ? "bg-[#DC2626] text-white"
                          : act.status === "running"
                          ? "bg-[#2563EB] text-white animate-spin"
                          : "bg-slate-200 text-slate-500"
                      }`}
                    >
                      {act.status === "completed" ? "✓" : act.status === "failed" ? "✕" : "○"}
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-mono font-semibold text-xs text-[#0F172A]">
                          {act.action || act.action_type || `Action #${idx + 1}`}
                        </span>
                        {act.application && (
                          <span className={`text-[10px] font-medium px-2 py-0.5 rounded border shrink-0 ${getAppBadgeClass(act.application)}`}>
                            {getApplicationDisplayName(act.application)}
                          </span>
                        )}
                      </div>
                      {act.message && (
                        <p className="text-[11px] text-[#64748B] mt-0.5 break-words">
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
                    onClick={() => setSelectedExecution(exec)}
                    className="hover:bg-[#F8FAFC] transition-colors duration-150 animate-row-enter cursor-pointer group"
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
                      {exec.execution_id}
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
                        className="px-2.5 py-1 text-xs font-semibold rounded bg-white hover:bg-[#F8FAFC] border border-[#E2E8F0] text-[#2563EB] shadow-2xs transition-all duration-150 active:translate-y-px cursor-pointer"
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
