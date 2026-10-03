"use client";

import React, { useState } from "react";
import { AutomationExecutionRecord, ActionDetail } from "@/lib/types";
import { statusBadgeConfig, getApplicationDisplayName } from "@/lib/utils";
import { API_BASE_URL } from "@/lib/utils";

interface ExecutionsViewProps {
  executions: AutomationExecutionRecord[];
  loading: boolean;
  onRefresh: () => void;
}

function ExecutionDetailModal({
  execution,
  onClose,
  onRefresh,
}: {
  execution: AutomationExecutionRecord;
  onClose: () => void;
  onRefresh: () => void;
}) {
  const [isResuming, setIsResuming] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const handleResume = async () => {
    setIsResuming(true);
    setActionError(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/automation/executions/${execution.execution_id}/resume`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ executor_type: "playwright" }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Resume failed (${res.status})`);
      }
      onRefresh();
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
      const res = await fetch(`${API_BASE_URL}/api/automation/executions/${execution.execution_id}/cancel`, { method: "POST" });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Cancel failed (${res.status})`);
      }
      onRefresh();
      onClose();
    } catch (e: unknown) {
      setActionError(e instanceof Error ? e.message : "Cancel failed");
    } finally {
      setIsCancelling(false);
    }
  };

  const cfg = statusBadgeConfig(execution.status);
  const actions: ActionDetail[] = execution.all_actions || execution.actions_detail || [];
  const progress = execution.total_actions > 0
    ? Math.round((execution.completed_actions.length / execution.total_actions) * 100)
    : 0;

  return (
    <div
      className="fixed inset-0 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4 z-50"
      onClick={onClose}
    >
      <div
        className="bg-zinc-900 border border-zinc-700/80 rounded-2xl max-w-2xl w-full shadow-2xl flex flex-col max-h-[90vh] overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-6 py-4 border-b border-zinc-800 flex items-start justify-between shrink-0">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className={`text-xs font-semibold px-2 py-0.5 rounded-full border ${cfg.className}`}>
                {cfg.label}
              </span>
              <code className="text-[10px] font-mono text-zinc-600 bg-zinc-950 px-1.5 py-0.5 rounded border border-zinc-800">
                {execution.execution_id}
              </code>
            </div>
            <h3 className="text-lg font-bold text-white">{execution.workflow_name || "Automation Workflow"}</h3>
          </div>
          <button onClick={onClose} className="text-zinc-500 hover:text-white p-1 rounded-lg hover:bg-zinc-800 transition cursor-pointer">✕</button>
        </div>

        {/* Body */}
        <div className="overflow-y-auto flex-1 px-6 py-4 space-y-5">
          {/* Meta row */}
          <div className="grid grid-cols-3 gap-3 text-center">
            <div className="bg-zinc-950/60 border border-zinc-800 rounded-lg py-3">
              <div className="text-lg font-bold font-mono text-white">
                {execution.completed_actions.length}/{execution.total_actions}
              </div>
              <div className="text-[10px] text-zinc-500 mt-0.5">Steps Done</div>
            </div>
            <div className="bg-zinc-950/60 border border-zinc-800 rounded-lg py-3">
              <div className="text-lg font-bold font-mono text-white">
                {execution.execution_time_seconds != null ? `${execution.execution_time_seconds}s` : "—"}
              </div>
              <div className="text-[10px] text-zinc-500 mt-0.5">Duration</div>
            </div>
            <div className="bg-zinc-950/60 border border-zinc-800 rounded-lg py-3">
              <div className="text-lg font-bold font-mono text-white">{execution.resume_count ?? 0}</div>
              <div className="text-[10px] text-zinc-500 mt-0.5">Resumes</div>
            </div>
          </div>

          {/* Progress bar */}
          <div>
            <div className="flex items-center justify-between text-[11px] text-zinc-500 mb-1.5">
              <span>Execution Progress</span>
              <span>{progress}%</span>
            </div>
            <div className="h-2 bg-zinc-800 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-500 ${
                  execution.status === "completed" ? "bg-emerald-500"
                  : execution.status === "failed" ? "bg-rose-500"
                  : execution.status === "paused" ? "bg-amber-500"
                  : execution.status === "cancelled" ? "bg-zinc-600"
                  : "bg-indigo-500"
                }`}
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>

          {/* Timestamps */}
          {(execution.started_at || execution.completed_at || execution.paused_at) && (
            <div className="bg-zinc-950/50 border border-zinc-800/60 rounded-xl p-4 text-xs space-y-1.5">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500 mb-2">Timeline</p>
              {execution.started_at && (
                <div className="flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-cyan-500 shrink-0" />
                  <span className="text-zinc-500">Started:</span>
                  <span className="text-zinc-300 font-mono">{new Date(execution.started_at).toLocaleString()}</span>
                </div>
              )}
              {execution.paused_at && (
                <div className="flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-500 shrink-0" />
                  <span className="text-zinc-500">Paused:</span>
                  <span className="text-zinc-300 font-mono">{new Date(execution.paused_at).toLocaleString()}</span>
                </div>
              )}
              {execution.resumed_at && (
                <div className="flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 shrink-0" />
                  <span className="text-zinc-500">Resumed:</span>
                  <span className="text-zinc-300 font-mono">{new Date(execution.resumed_at).toLocaleString()}</span>
                </div>
              )}
              {execution.completed_at && (
                <div className="flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0" />
                  <span className="text-zinc-500">Completed:</span>
                  <span className="text-zinc-300 font-mono">{new Date(execution.completed_at).toLocaleString()}</span>
                </div>
              )}
            </div>
          )}

          {/* Failure reason */}
          {(execution.failure_reason || execution.error || execution.failed_action) && (
            <div className="bg-rose-950/30 border border-rose-800/50 rounded-xl p-4">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-rose-400 mb-1.5">Failure Details</p>
              {execution.failure_reason && <p className="text-sm text-rose-300">{execution.failure_reason}</p>}
              {execution.error && !execution.failure_reason && <p className="text-sm text-rose-300">{execution.error}</p>}
              {execution.failed_action && (
                <p className="text-xs text-rose-400/70 mt-1">Failed at step: <code className="text-rose-300">{execution.failed_action}</code></p>
              )}
              {execution.requires_human_intervention && (
                <span className="inline-block mt-2 text-[10px] font-semibold bg-amber-950/60 border border-amber-600/40 text-amber-300 px-2 py-0.5 rounded">
                  Human intervention required
                </span>
              )}
            </div>
          )}

          {/* Applications */}
          {execution.applications && execution.applications.length > 0 && (
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500 mb-2">Applications Involved</p>
              <div className="flex flex-wrap gap-2">
                {execution.applications.map((app, i) => (
                  <span key={i} className="px-2.5 py-1 rounded text-xs font-medium bg-zinc-800 border border-zinc-700 text-zinc-300">
                    {getApplicationDisplayName(app)}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Step-by-step timeline */}
          {actions.length > 0 && (
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500 mb-3">Step Timeline</p>
              <div className="space-y-2">
                {actions.map((a, i) => (
                  <div key={i} className={`flex items-start gap-3 p-3 rounded-lg border ${
                    a.status === "completed" ? "bg-emerald-950/20 border-emerald-900/40"
                    : a.status === "failed" ? "bg-rose-950/20 border-rose-900/40"
                    : a.status === "skipped" ? "bg-zinc-900/40 border-zinc-800/40"
                    : "bg-zinc-900/40 border-zinc-800/40"
                  }`}>
                    <span className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold shrink-0 mt-0.5 ${
                      a.status === "completed" ? "bg-emerald-900 text-emerald-300 border border-emerald-700"
                      : a.status === "failed" ? "bg-rose-900 text-rose-300 border border-rose-700"
                      : "bg-zinc-800 text-zinc-500 border border-zinc-700"
                    }`}>
                      {a.status === "completed" ? "✓" : a.status === "failed" ? "✗" : String(i + 1)}
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-xs font-medium text-zinc-200 font-mono">{a.action}</span>
                        {a.description && <span className="text-xs text-zinc-500">— {a.description}</span>}
                      </div>
                      {a.target && <p className="text-[11px] text-zinc-600 mt-0.5 font-mono">target: {a.target}</p>}
                      {a.message && <p className="text-[11px] text-zinc-500 mt-0.5">{a.message}</p>}
                    </div>
                    <span className="text-[10px] font-mono text-zinc-600 shrink-0">{a.application}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Action error */}
          {actionError && (
            <div className="bg-rose-950/40 border border-rose-800/60 rounded-xl p-3 text-xs text-rose-300">
              <span className="font-semibold">Error: </span>{actionError}
            </div>
          )}
        </div>

        {/* Footer: intervention controls */}
        {(execution.status === "paused" && execution.resume_available) && (
          <div className="px-6 py-4 border-t border-zinc-800 shrink-0 bg-amber-950/20 flex items-center justify-between gap-4">
            <div>
              <p className="text-sm font-semibold text-amber-300">Human Review Required</p>
              <p className="text-xs text-amber-400/70">Review the failure reason above, then resume or cancel.</p>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={handleCancel}
                disabled={isResuming || isCancelling}
                className="px-3.5 py-1.5 text-xs font-medium rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 border border-zinc-700 transition active:scale-95 disabled:opacity-60 cursor-pointer"
              >
                {isCancelling ? "Cancelling…" : "Cancel"}
              </button>
              <button
                onClick={handleResume}
                disabled={isResuming || isCancelling}
                className="px-4 py-1.5 text-xs font-semibold rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white transition active:scale-95 disabled:opacity-60 cursor-pointer"
              >
                {isResuming ? "Resuming…" : "Resume Execution"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function ExecutionsView({ executions, loading, onRefresh }: ExecutionsViewProps) {
  const [selectedExecution, setSelectedExecution] = useState<AutomationExecutionRecord | null>(null);
  const [statusFilter, setStatusFilter] = useState("ALL");

  const filtered = executions.filter((e) => statusFilter === "ALL" || e.status === statusFilter);

  const statuses = ["ALL", "completed", "paused", "failed", "cancelled", "running", "pending"];

  return (
    <div className="p-6 space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold text-white">Execution History</h2>
          <p className="text-xs text-zinc-500 mt-0.5">Automation run history, status and human intervention controls</p>
        </div>
        <button
          onClick={onRefresh}
          disabled={loading}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 text-zinc-200 transition active:scale-95 disabled:opacity-60 cursor-pointer"
        >
          <svg className={`w-3.5 h-3.5 ${loading ? "animate-spin text-cyan-400" : "text-zinc-400"}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          Refresh
        </button>
      </div>

      {/* Status filter tabs */}
      <div className="flex items-center gap-1.5 overflow-x-auto pb-1 scrollbar-hide">
        {statuses.map((s) => {
          const count = s === "ALL" ? executions.length : executions.filter((e) => e.status === s).length;
          if (count === 0 && s !== "ALL") return null;
          return (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition cursor-pointer border ${
                statusFilter === s
                  ? "bg-indigo-950/80 border-indigo-700/50 text-indigo-300"
                  : "bg-zinc-900/60 border-zinc-800/60 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/60"
              }`}
            >
              <span className="capitalize">{s === "ALL" ? "All" : s}</span>
              <span className={`text-[10px] font-mono px-1 py-0.5 rounded ${
                statusFilter === s ? "bg-indigo-900/60 text-indigo-400" : "bg-zinc-800 text-zinc-500"
              }`}>{count}</span>
            </button>
          );
        })}
      </div>

      {/* Table */}
      <section className="bg-zinc-900/50 border border-zinc-800/80 rounded-xl overflow-hidden">
        {loading ? (
          <div className="p-6 space-y-4">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="flex gap-4 animate-pulse">
                <div className="h-5 w-5 bg-zinc-800 rounded-full" />
                <div className="flex-1 space-y-1.5">
                  <div className="h-4 w-48 bg-zinc-800 rounded" />
                  <div className="h-3 w-32 bg-zinc-800 rounded" />
                </div>
                <div className="h-5 w-20 bg-zinc-800 rounded-full" />
              </div>
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="py-16 text-center px-4">
            <div className="w-12 h-12 rounded-full bg-zinc-800/60 border border-zinc-700/50 text-zinc-500 flex items-center justify-center mx-auto mb-3">
              <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <p className="text-sm font-medium text-zinc-300">
              {executions.length === 0 ? "No executions recorded yet" : `No ${statusFilter} executions`}
            </p>
            <p className="text-xs text-zinc-500 mt-1">
              {executions.length === 0 ? "Approve a workflow from the Discovery view to start automation." : "Try a different status filter."}
            </p>
          </div>
        ) : (
          <div className="divide-y divide-zinc-800/60">
            {filtered.map((ex) => {
              const cfg = statusBadgeConfig(ex.status);
              const progress = ex.total_actions > 0 ? (ex.completed_actions.length / ex.total_actions) * 100 : 0;
              return (
                <div key={ex.execution_id} className="p-4 hover:bg-zinc-800/25 transition">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2.5 flex-wrap mb-1">
                        <span className="font-semibold text-white text-sm truncate">
                          {ex.workflow_name || "Automation Workflow"}
                        </span>
                        <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${cfg.className}`}>
                          {cfg.dot && <span className={`inline-block w-1.5 h-1.5 rounded-full ${cfg.dot} mr-1`} />}
                          {cfg.label}
                        </span>
                        {ex.resume_count && ex.resume_count > 0 && (
                          <span className="text-[10px] font-mono text-amber-300 bg-amber-950/40 border border-amber-800/40 px-1.5 py-0.5 rounded">
                            {ex.resume_count}× resumed
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-3 text-xs text-zinc-500 flex-wrap">
                        <span><strong className="text-zinc-300">{ex.completed_actions.length}/{ex.total_actions}</strong> actions</span>
                        {ex.execution_time_seconds != null && (
                          <span>• <strong className="text-zinc-300">{ex.execution_time_seconds}s</strong></span>
                        )}
                        {ex.started_at && (
                          <span>• {new Date(ex.started_at).toLocaleString()}</span>
                        )}
                        {ex.applications && ex.applications.length > 0 && (
                          <span>• {ex.applications.map(getApplicationDisplayName).join(", ")}</span>
                        )}
                      </div>
                      {/* Failure hint */}
                      {(ex.status === "failed" || ex.status === "paused") && ex.failure_reason && (
                        <p className="text-xs text-rose-400/80 mt-1">{ex.failure_reason}</p>
                      )}
                      {/* Progress bar */}
                      <div className="mt-2.5 h-1 bg-zinc-800 rounded-full overflow-hidden w-full max-w-xs">
                        <div
                          className={`h-full rounded-full transition-all ${
                            ex.status === "completed" ? "bg-emerald-500"
                            : ex.status === "failed" ? "bg-rose-500"
                            : ex.status === "paused" ? "bg-amber-500"
                            : ex.status === "cancelled" ? "bg-zinc-600"
                            : "bg-indigo-500"
                          }`}
                          style={{ width: `${progress}%` }}
                        />
                      </div>
                    </div>

                    {/* Inspect button */}
                    <button
                      onClick={() => setSelectedExecution(ex)}
                      className="shrink-0 px-3.5 py-1.5 text-xs font-medium rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border border-zinc-700 transition active:scale-95 cursor-pointer flex items-center gap-1.5"
                    >
                      <svg className="w-3.5 h-3.5 text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                      </svg>
                      Inspect
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* Detail Modal */}
      {selectedExecution && (
        <ExecutionDetailModal
          execution={selectedExecution}
          onClose={() => setSelectedExecution(null)}
          onRefresh={() => { onRefresh(); setSelectedExecution(null); }}
        />
      )}
    </div>
  );
}
