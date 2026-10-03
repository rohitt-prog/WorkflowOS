"use client";

import React, { useState, useCallback } from "react";
import {
  DiscoveryResult,
  DiscoveredWorkflow,
  WorkflowProposal,
  AutomationExecutionResponse,
  ApprovalStatus,
} from "@/lib/types";
import { API_BASE_URL, formatEventStep, getAppBadgeClass } from "@/lib/utils";

interface DiscoveryViewProps {
  discovery: DiscoveryResult | null;
  discoveryLoading: boolean;
  discoveryError: string | null;
  onRefreshDiscovery: () => void;
  onExecutionComplete: () => void;
}

export default function DiscoveryView({
  discovery,
  discoveryLoading,
  discoveryError,
  onRefreshDiscovery,
  onExecutionComplete,
}: DiscoveryViewProps) {
  const [reviewWorkflow, setReviewWorkflow] = useState<DiscoveredWorkflow | null>(null);
  const [proposal, setProposal] = useState<WorkflowProposal | null>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState<string | null>(null);
  const [approvals, setApprovals] = useState<Record<string, "approved" | "rejected">>({});
  const [isExecuting, setIsExecuting] = useState(false);
  const [isResuming, setIsResuming] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);
  const [executionResult, setExecutionResult] = useState<AutomationExecutionResponse | null>(null);
  const [executionError, setExecutionError] = useState<string | null>(null);
  const [testCustomer, setTestCustomer] = useState("Rahul");
  const [approvalStatus, setApprovalStatus] = useState<ApprovalStatus>("idle");

  const handleReview = useCallback(async (wf: DiscoveredWorkflow) => {
    setReviewWorkflow(wf);
    setProposal(null);
    setAiLoading(true);
    setAiError(null);
    setExecutionResult(null);
    setExecutionError(null);
    setApprovalStatus(approvals[wf.label] || "idle");

    try {
      const res = await fetch(`${API_BASE_URL}/api/ai/workflow/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          workflow: wf,
          sequence: wf.sequence,
          context: { label: wf.label, occurrences: wf.occurrences, similarity: wf.similarity },
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Server returned ${res.status}`);
      }
      const data = await res.json();
      if (data.success && data.workflow) {
        setProposal(data.workflow);
      } else {
        throw new Error(data.error || "No proposal returned");
      }
    } catch (e: unknown) {
      setAiError(e instanceof Error ? e.message : "AI analysis failed");
    } finally {
      setAiLoading(false);
    }
  }, [approvals]);

  const handleApproveAndRun = async () => {
    if (!proposal) return;
    setIsExecuting(true);
    setExecutionError(null);
    setExecutionResult(null);

    const updatedActions = proposal.actions.map((act) =>
      act.type === "search_customer" || act.type === "update_customer"
        ? { ...act, target: testCustomer }
        : act
    );

    try {
      const res = await fetch(`${API_BASE_URL}/api/automation/execute`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          workflow: { ...proposal, actions: updatedActions },
          approved: true,
          session_id: reviewWorkflow?.session_ids?.[0],
          parameters: { customer_name: testCustomer },
          executor_type: "playwright",
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Error ${res.status}`);
      }
      const data: AutomationExecutionResponse = await res.json();
      setExecutionResult(data);
      setApprovalStatus("approved");
      if (reviewWorkflow) setApprovals((prev) => ({ ...prev, [reviewWorkflow.label]: "approved" }));
      onExecutionComplete();
    } catch (e: unknown) {
      setExecutionError(e instanceof Error ? e.message : "Execution failed");
    } finally {
      setIsExecuting(false);
      onExecutionComplete();
    }
  };

  const handleResume = async () => {
    if (!executionResult?.workflow_id) return;
    setIsResuming(true);
    setExecutionError(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/automation/executions/${executionResult.workflow_id}/resume`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ executor_type: "playwright", parameters: { customer_name: testCustomer }, context: { customer_name: testCustomer } }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Resume failed ${res.status}`);
      }
      const data: AutomationExecutionResponse = await res.json();
      setExecutionResult(data);
      if (data.status === "completed") {
        setApprovalStatus("approved");
        if (reviewWorkflow) setApprovals((prev) => ({ ...prev, [reviewWorkflow.label]: "approved" }));
      }
      onExecutionComplete();
    } catch (e: unknown) {
      setExecutionError(e instanceof Error ? e.message : "Resume failed");
    } finally {
      setIsResuming(false);
      onExecutionComplete();
    }
  };

  const handleCancel = async () => {
    if (!executionResult?.workflow_id) return;
    setIsCancelling(true);
    setExecutionError(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/automation/executions/${executionResult.workflow_id}/cancel`, { method: "POST" });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Cancel failed ${res.status}`);
      }
      const data: AutomationExecutionResponse = await res.json();
      setExecutionResult(data);
      onExecutionComplete();
    } catch (e: unknown) {
      setExecutionError(e instanceof Error ? e.message : "Cancel failed");
    } finally {
      setIsCancelling(false);
      onExecutionComplete();
    }
  };

  return (
    <div className="p-6 space-y-5">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold text-white">Workflow Discovery</h2>
          <p className="text-xs text-zinc-500 mt-0.5">Repeated patterns detected from your activity sessions</p>
        </div>
        <button
          onClick={onRefreshDiscovery}
          disabled={discoveryLoading}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 text-zinc-200 transition active:scale-95 disabled:opacity-60 cursor-pointer"
        >
          <svg className={`w-3.5 h-3.5 ${discoveryLoading ? "animate-spin text-indigo-400" : "text-zinc-400"}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          Scan Again
        </button>
      </div>

      {/* Loading */}
      {discoveryLoading && (
        <div className="flex items-center gap-3 py-8 text-zinc-400 text-sm">
          <div className="w-4 h-4 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin" />
          Scanning event history for repeated workflow patterns…
        </div>
      )}

      {/* Error */}
      {!discoveryLoading && discoveryError && (
        <div className="bg-amber-950/30 border border-amber-800/60 rounded-xl p-4 flex items-start gap-3">
          <svg className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <div>
            <p className="text-sm font-medium text-amber-300">Discovery Unavailable</p>
            <p className="text-xs text-amber-400/70 mt-0.5">{discoveryError}</p>
          </div>
        </div>
      )}

      {/* No patterns */}
      {!discoveryLoading && !discoveryError && (!discovery || !discovery.detected) && (
        <div className="py-16 text-center bg-zinc-900/40 border border-zinc-800/60 rounded-xl">
          <div className="w-12 h-12 rounded-xl bg-zinc-800/60 border border-zinc-700/50 flex items-center justify-center mx-auto text-zinc-500 mb-3">
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>
          <h3 className="text-sm font-semibold text-zinc-300">No Repeated Workflows Detected</h3>
          <p className="text-xs text-zinc-500 mt-1 max-w-sm mx-auto">
            WorkFlowOS needs at least 2 sessions sharing a sequence of ≥3 events.
          </p>
          <div className="mt-4 inline-block text-left bg-zinc-950 border border-zinc-800 rounded-lg p-3 text-xs">
            <p className="text-zinc-500 font-mono text-[11px] mb-1">Seed test data:</p>
            <code className="text-indigo-400 font-mono select-all">python backend/test_event.py --seed-workflows</code>
          </div>
        </div>
      )}

      {/* Workflow cards */}
      {!discoveryLoading && !discoveryError && discovery?.detected && (
        <div className="space-y-4">
          <div className="flex items-center gap-3 bg-emerald-950/30 border border-emerald-800/50 rounded-lg px-4 py-3">
            <svg className="w-5 h-5 text-emerald-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div>
              <p className="text-sm font-semibold text-emerald-300">
                {discovery.workflows.length} workflow pattern{discovery.workflows.length > 1 ? "s" : ""} detected
              </p>
              <p className="text-xs text-emerald-500/80">Patterns found across multiple activity sessions</p>
            </div>
          </div>

          {discovery.workflows.map((wf, idx) => (
            <div key={idx} className="bg-zinc-900/60 border border-zinc-800/80 rounded-xl overflow-hidden">
              <div className="p-5">
                <div className="flex flex-wrap items-start justify-between gap-4 mb-4">
                  <div>
                    <h3 className="text-base font-bold text-white">{wf.label}</h3>
                    <p className="text-xs text-zinc-500 mt-0.5">Deterministic workflow pattern</p>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="text-center">
                      <div className="text-lg font-bold font-mono text-indigo-300">{wf.occurrences}×</div>
                      <div className="text-[10px] text-zinc-600 uppercase tracking-wider">Repeated</div>
                    </div>
                    <div className="text-center">
                      <div className="text-lg font-bold font-mono text-emerald-300">{Math.round(wf.similarity * 100)}%</div>
                      <div className="text-[10px] text-zinc-600 uppercase tracking-wider">Similarity</div>
                    </div>
                  </div>
                </div>

                {/* Sequence steps */}
                <div className="mb-4">
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500 mb-2">Workflow Steps</p>
                  <div className="flex flex-wrap items-center gap-1.5">
                    {wf.sequence.map((step, si) => (
                      <React.Fragment key={si}>
                        <span className="px-2.5 py-1 rounded text-xs font-mono bg-indigo-950/60 text-indigo-200 border border-indigo-800/50">
                          {formatEventStep(step)}
                        </span>
                        {si < wf.sequence.length - 1 && (
                          <svg className="w-3 h-3 text-zinc-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                          </svg>
                        )}
                      </React.Fragment>
                    ))}
                  </div>
                </div>

                {/* Sessions */}
                <div className="mb-4">
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500 mb-2">Sessions</p>
                  <div className="flex flex-wrap gap-2">
                    {wf.session_ids.map((sid) => (
                      <span key={sid} className="px-2 py-0.5 rounded text-[11px] font-mono bg-zinc-800 text-zinc-400 border border-zinc-700/50">
                        {sid}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              {/* Footer */}
              <div className="px-5 py-3.5 border-t border-zinc-800/60 bg-zinc-900/30 flex items-center justify-between gap-4">
                <div>
                  {approvals[wf.label] === "approved" && (
                    <div className="flex items-center gap-1.5 text-xs text-emerald-400">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                      Approved and executed
                    </div>
                  )}
                  {approvals[wf.label] === "rejected" && (
                    <div className="flex items-center gap-1.5 text-xs text-zinc-500">
                      <span className="w-1.5 h-1.5 rounded-full bg-zinc-500" />
                      Rejected
                    </div>
                  )}
                  {!approvals[wf.label] && (
                    <p className="text-xs text-zinc-600 italic">Review and generate AI automation proposal</p>
                  )}
                </div>
                <button
                  id={`review-workflow-btn-${idx}`}
                  onClick={() => handleReview(wf)}
                  className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white border border-indigo-500/50 active:scale-95 transition cursor-pointer shadow-md shadow-indigo-950/50"
                >
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                  Review & Generate
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Review modal / drawer */}
      {reviewWorkflow && (
        <div
          className="fixed inset-0 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4 z-50"
          onClick={() => { if (!aiLoading) setReviewWorkflow(null); }}
        >
          <div
            id="workflow-review-modal"
            className="bg-zinc-900 border border-zinc-700/80 rounded-2xl max-w-2xl w-full shadow-2xl flex flex-col max-h-[90vh] overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal header */}
            <div className="px-6 py-4 border-b border-zinc-800 flex items-start justify-between shrink-0">
              <div>
                <span className="text-[10px] font-mono font-semibold text-indigo-400 uppercase tracking-wider">
                  AI Workflow Proposal · Gemini
                </span>
                <h3 className="text-lg font-bold text-white mt-0.5">
                  {proposal ? proposal.name : reviewWorkflow.label}
                </h3>
              </div>
              <button
                onClick={() => setReviewWorkflow(null)}
                disabled={aiLoading}
                className="text-zinc-500 hover:text-white p-1 rounded-lg hover:bg-zinc-800 transition disabled:opacity-40 cursor-pointer"
              >✕</button>
            </div>

            {/* Modal body */}
            <div className="overflow-y-auto flex-1 px-6 py-4 space-y-4">
              {/* AI Loading */}
              {aiLoading && (
                <div className="py-12 text-center space-y-4">
                  <div className="relative w-12 h-12 mx-auto">
                    <div className="absolute inset-0 rounded-full border-2 border-indigo-500/20 animate-ping" />
                    <div className="w-12 h-12 rounded-full border-2 border-indigo-500 border-t-cyan-400 animate-spin" />
                  </div>
                  <p className="text-sm text-zinc-300 font-medium">Analysing workflow with Gemini…</p>
                  <p className="text-xs text-zinc-500 max-w-xs mx-auto">
                    Inferring intent, trigger, actions and variables from observed sequence.
                  </p>
                  <div className="flex flex-wrap justify-center gap-1.5 pt-2">
                    {reviewWorkflow.sequence.map((step, idx) => (
                      <span key={idx} className="px-2.5 py-1 rounded text-xs font-mono bg-zinc-800 text-zinc-300 border border-zinc-700/50">
                        {formatEventStep(step)}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* AI Error */}
              {!aiLoading && aiError && (
                <div className="bg-rose-950/40 border border-rose-800/60 rounded-xl p-4">
                  <p className="text-sm font-semibold text-rose-300">Analysis Failed</p>
                  <p className="text-xs text-rose-400/80 mt-1">{aiError}</p>
                  <p className="text-[11px] text-zinc-500 mt-2">
                    Ensure <code className="text-indigo-300">GEMINI_API_KEY</code> is set in your <code>.env</code> file.
                  </p>
                  <div className="mt-3 flex gap-2">
                    <button onClick={() => handleReview(reviewWorkflow)} className="px-3 py-1.5 text-xs font-medium rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white transition cursor-pointer">
                      Retry
                    </button>
                    <button onClick={() => setReviewWorkflow(null)} className="px-3 py-1.5 text-xs rounded-lg bg-zinc-800 text-zinc-300 hover:bg-zinc-700 transition cursor-pointer">
                      Dismiss
                    </button>
                  </div>
                </div>
              )}

              {/* Proposal */}
              {!aiLoading && !aiError && proposal && (
                <>
                  {/* Intent */}
                  <div className="bg-zinc-950/70 rounded-xl p-4 border border-zinc-800">
                    <p className="text-[10px] font-mono uppercase tracking-wider text-indigo-400 font-semibold mb-1">Intent</p>
                    <p className="text-sm text-zinc-200 leading-relaxed">{proposal.intent}</p>
                  </div>

                  {/* Trigger */}
                  <div className="bg-zinc-950/70 rounded-xl p-4 border border-zinc-800">
                    <div className="flex items-center justify-between mb-2">
                      <p className="text-[10px] font-mono uppercase tracking-wider text-cyan-400 font-semibold">Trigger</p>
                      <span className={`px-2 py-0.5 rounded text-[10px] font-mono border ${getAppBadgeClass(proposal.trigger.application)}`}>
                        {proposal.trigger.application}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs text-white bg-zinc-800 px-2 py-0.5 rounded border border-zinc-700">
                        {proposal.trigger.type}
                      </span>
                      <span className="text-xs text-zinc-400">{proposal.trigger.description}</span>
                    </div>
                  </div>

                  {/* Steps */}
                  <div className="bg-zinc-950/70 rounded-xl p-4 border border-zinc-800">
                    <p className="text-[10px] font-mono uppercase tracking-wider text-purple-400 font-semibold mb-3">
                      Actions ({proposal.actions.length} Steps)
                    </p>
                    <div className="space-y-2">
                      {proposal.actions.map((act, i) => (
                        <div key={i} className="flex items-start justify-between gap-3 p-2.5 rounded-lg bg-zinc-900/60 border border-zinc-800/50">
                          <div className="flex items-start gap-3">
                            <span className="w-5 h-5 rounded-full bg-indigo-950 text-indigo-300 border border-indigo-800/60 flex items-center justify-center text-xs font-mono font-bold shrink-0 mt-0.5">
                              {i + 1}
                            </span>
                            <div>
                              <p className="text-xs font-medium text-white">{act.description}</p>
                              <div className="flex items-center gap-2 mt-1 flex-wrap">
                                <span className="font-mono text-[11px] text-cyan-300 bg-cyan-950/30 px-1.5 py-0.5 rounded border border-cyan-800/40">
                                  {act.type}
                                </span>
                                {act.target && (
                                  <span className="font-mono text-[11px] text-zinc-500">
                                    target: <code className="text-zinc-300">{act.target}</code>
                                  </span>
                                )}
                              </div>
                            </div>
                          </div>
                          <span className={`px-2 py-0.5 rounded text-[10px] font-mono border shrink-0 ${getAppBadgeClass(act.application)}`}>
                            {act.application}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Variables + Apps */}
                  <div className="grid grid-cols-2 gap-3">
                    <div className="bg-zinc-950/70 rounded-xl p-4 border border-zinc-800">
                      <p className="text-[10px] font-mono uppercase tracking-wider text-amber-400 font-semibold mb-2">Variables</p>
                      <div className="flex flex-wrap gap-1.5">
                        {proposal.variables?.length > 0 ? proposal.variables.map((v, vi) => (
                          <span key={vi} className="px-2 py-0.5 rounded text-xs font-mono bg-amber-950/40 text-amber-300 border border-amber-800/50">
                            ${v}
                          </span>
                        )) : <span className="text-xs text-zinc-600 italic">None detected</span>}
                      </div>
                    </div>
                    <div className="bg-zinc-950/70 rounded-xl p-4 border border-zinc-800">
                      <p className="text-[10px] font-mono uppercase tracking-wider text-emerald-400 font-semibold mb-2">Applications</p>
                      <div className="flex flex-wrap gap-1.5">
                        {proposal.applications.map((app, ai) => (
                          <span key={ai} className={`px-2 py-0.5 rounded text-xs font-mono border ${getAppBadgeClass(app)}`}>{app}</span>
                        ))}
                      </div>
                    </div>
                  </div>

                  {/* Customer target switcher */}
                  <div className="bg-zinc-950/70 rounded-xl p-4 border border-zinc-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    <div>
                      <p className="text-[10px] font-mono uppercase tracking-wider text-cyan-400 font-semibold">Test Customer</p>
                      <p className="text-xs text-zinc-500">Happy Path vs. human intervention demo</p>
                    </div>
                    <div className="flex items-center gap-2">
                      {["Rahul", "Unknown Customer"].map((name) => (
                        <button
                          key={name}
                          onClick={() => setTestCustomer(name)}
                          className={`px-3 py-1.5 rounded-lg text-xs font-mono font-medium transition cursor-pointer ${
                            testCustomer === name
                              ? name === "Rahul"
                                ? "bg-cyan-600 text-white border border-cyan-400"
                                : "bg-amber-600 text-white border border-amber-400"
                              : "bg-zinc-800 text-zinc-400 hover:text-zinc-200 border border-zinc-700"
                          }`}
                        >
                          {name === "Rahul" ? "Rahul (Happy Path)" : "Unknown (Fail Demo)"}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Execution in-progress */}
                  {isExecuting && (
                    <div className="bg-cyan-950/40 border border-cyan-500/40 rounded-xl p-4 flex items-center gap-3">
                      <div className="w-4 h-4 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin shrink-0" />
                      <div>
                        <p className="text-sm font-semibold text-cyan-300">Executing automation…</p>
                        <p className="text-xs text-cyan-400/70">Running actions via PlaywrightExecutor</p>
                      </div>
                    </div>
                  )}

                  {/* Execution error */}
                  {executionError && (
                    <div className="bg-rose-950/40 border border-rose-800/60 rounded-xl p-3 text-xs text-rose-300">
                      <span className="font-semibold">Error: </span>{executionError}
                    </div>
                  )}

                  {/* Execution result */}
                  {executionResult && !isExecuting && (
                    <div className={`rounded-xl p-4 border ${
                      executionResult.status === "completed" ? "bg-emerald-950/30 border-emerald-700/50"
                      : executionResult.status === "paused" ? "bg-amber-950/30 border-amber-700/50"
                      : executionResult.status === "cancelled" ? "bg-zinc-900 border-zinc-700"
                      : "bg-rose-950/30 border-rose-700/50"
                    }`}>
                      <div className="flex items-center justify-between mb-2">
                        <p className={`text-sm font-semibold ${
                          executionResult.status === "completed" ? "text-emerald-300"
                          : executionResult.status === "paused" ? "text-amber-300"
                          : executionResult.status === "cancelled" ? "text-zinc-400"
                          : "text-rose-300"
                        }`}>
                          {executionResult.status === "completed" ? "✓ Automation Completed"
                          : executionResult.status === "paused" ? "⏸ Paused — Human Intervention Required"
                          : executionResult.status === "cancelled" ? "✕ Cancelled"
                          : "⚠ Automation Stopped"}
                        </p>
                        <span className="text-[10px] font-mono text-zinc-500">
                          {executionResult.completed_actions.length}/{executionResult.total_actions} steps
                        </span>
                      </div>

                      {executionResult.human_intervention && (
                        <div className="bg-amber-950/40 border border-amber-800/40 rounded-lg p-3 mb-3">
                          <p className="text-xs font-semibold text-amber-300">{executionResult.human_intervention.title}</p>
                          <p className="text-xs text-amber-400/80 mt-1">{executionResult.human_intervention.reason}</p>
                          <p className="text-xs text-amber-300/70 mt-1 italic">{executionResult.human_intervention.action_required}</p>
                        </div>
                      )}

                      {/* Steps */}
                      {executionResult.all_actions && executionResult.all_actions.length > 0 && (
                        <div className="space-y-1 mt-2">
                          {executionResult.all_actions.map((a, i) => (
                            <div key={i} className="flex items-center gap-2 text-xs">
                              <span className={`w-4 h-4 rounded-full flex items-center justify-center text-[10px] font-bold ${
                                a.status === "completed" ? "bg-emerald-900/60 text-emerald-300"
                                : a.status === "failed" ? "bg-rose-900/60 text-rose-300"
                                : a.status === "skipped" ? "bg-zinc-800 text-zinc-500"
                                : "bg-zinc-800 text-zinc-500"
                              }`}>
                                {a.status === "completed" ? "✓" : a.status === "failed" ? "✗" : "○"}
                              </span>
                              <span className={`font-mono ${a.status === "completed" ? "text-zinc-300" : a.status === "failed" ? "text-rose-400" : "text-zinc-500"}`}>
                                {a.action}
                              </span>
                              {a.message && <span className="text-zinc-600">— {a.message}</span>}
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Resume / Cancel controls */}
                      {executionResult.status === "paused" && executionResult.resume_available && (
                        <div className="flex items-center gap-2 mt-3">
                          <button
                            onClick={handleResume}
                            disabled={isResuming || isCancelling}
                            className="px-4 py-1.5 text-xs font-semibold rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white transition active:scale-95 disabled:opacity-60 cursor-pointer"
                          >
                            {isResuming ? "Resuming…" : "Resume Execution"}
                          </button>
                          <button
                            onClick={handleCancel}
                            disabled={isResuming || isCancelling}
                            className="px-3.5 py-1.5 text-xs font-medium rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 border border-zinc-700 transition active:scale-95 disabled:opacity-60 cursor-pointer"
                          >
                            {isCancelling ? "Cancelling…" : "Cancel"}
                          </button>
                        </div>
                      )}
                    </div>
                  )}
                </>
              )}
            </div>

            {/* Modal footer */}
            {proposal && !aiLoading && !aiError && (
              <div className="px-6 py-4 border-t border-zinc-800 shrink-0 flex items-center justify-between gap-3 bg-zinc-950/40">
                <div className="flex items-center gap-2">
                  {approvalStatus === "approved" && (
                    <span className="text-xs text-emerald-400 font-medium">✓ Workflow approved</span>
                  )}
                  {approvalStatus === "rejected" && (
                    <span className="text-xs text-zinc-500">Workflow rejected</span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => {
                      setApprovalStatus("rejected");
                      if (reviewWorkflow) setApprovals((prev) => ({ ...prev, [reviewWorkflow.label]: "rejected" }));
                    }}
                    disabled={isExecuting || isResuming || approvalStatus !== "idle"}
                    className="px-3.5 py-1.5 text-xs font-medium rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 border border-zinc-700 transition disabled:opacity-50 cursor-pointer"
                  >
                    Reject
                  </button>
                  <button
                    onClick={handleApproveAndRun}
                    disabled={isExecuting || approvalStatus === "rejected" || (executionResult?.status === "completed")}
                    className="px-4 py-1.5 text-xs font-semibold rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white transition active:scale-95 disabled:opacity-50 cursor-pointer shadow-md shadow-indigo-950/50"
                  >
                    {isExecuting ? "Running…" : approvalStatus === "approved" ? "Run Again" : "Approve & Run"}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
