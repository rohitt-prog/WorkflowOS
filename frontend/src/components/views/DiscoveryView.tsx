"use client";

import React, { useState, useCallback } from "react";
import {
  DiscoveryResult,
  DiscoveredWorkflow,
  WorkflowProposal,
  AutomationExecutionResponse,
  ApprovalStatus,
} from "@/lib/types";
import { API_BASE_URL, formatEventStep, getAppBadgeClass, getApplicationDisplayName, formatApiErrorMessage } from "@/lib/utils";

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

  const handleReview = useCallback(
    async (wf: DiscoveredWorkflow) => {
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
            context: {
              label: wf.label,
              occurrences: wf.occurrences,
              similarity: wf.similarity,
            },
          }),
        });
        if (!res.ok) {
          const err = await res.json().catch(() => null);
          throw new Error(formatApiErrorMessage(err, `Server returned ${res.status}`));
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
    },
    [approvals]
  );

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

      const data: AutomationExecutionResponse = await res.json();
      setExecutionResult(data);

      if (data.status === "completed") {
        setApprovalStatus("approved");
        if (reviewWorkflow) {
          setApprovals((prev) => ({ ...prev, [reviewWorkflow.label]: "approved" }));
        }
        onExecutionComplete();
      } else if (data.status === "paused") {
        setApprovalStatus("approved");
        onExecutionComplete();
      } else {
        setExecutionError(data.message || "Execution encountered an error");
      }
    } catch (e: unknown) {
      setExecutionError(e instanceof Error ? e.message : "Failed to connect to execution API");
    } finally {
      setIsExecuting(false);
    }
  };

  const handleResume = async () => {
    if (!executionResult?.workflow_id) return;
    setIsResuming(true);
    setExecutionError(null);

    try {
      const res = await fetch(
        `${API_BASE_URL}/api/automation/executions/${executionResult.workflow_id}/resume`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ executor_type: "playwright" }),
        }
      );

      const data: AutomationExecutionResponse = await res.json();
      setExecutionResult(data);
      if (data.status === "completed") {
        onExecutionComplete();
      }
    } catch (e: unknown) {
      setExecutionError(e instanceof Error ? e.message : "Resume failed");
    } finally {
      setIsResuming(false);
    }
  };

  const handleCancel = async () => {
    if (!executionResult?.workflow_id) return;
    setIsCancelling(true);
    setExecutionError(null);

    try {
      const res = await fetch(
        `${API_BASE_URL}/api/automation/executions/${executionResult.workflow_id}/cancel`,
        { method: "POST" }
      );
      const data: AutomationExecutionResponse = await res.json();
      setExecutionResult(data);
      onExecutionComplete();
    } catch (e: unknown) {
      setExecutionError(e instanceof Error ? e.message : "Cancel failed");
    } finally {
      setIsCancelling(false);
    }
  };

  const closeModal = () => {
    setReviewWorkflow(null);
    setProposal(null);
    setExecutionResult(null);
    setExecutionError(null);
    setAiError(null);
  };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6 bg-[#F7F9FC]">
      {/* Header bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white border border-[#E2E8F0] rounded-xl p-5 shadow-2xs">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-bold text-[#0F172A] tracking-tight">
              Workflow Pattern Discovery
            </h2>
            {discovery?.detected && (
              <span className="text-[10px] font-semibold uppercase px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
                Active Patterns
              </span>
            )}
          </div>
          <p className="text-xs text-[#64748B] mt-0.5">
            Algorithmic contiguous repetition detection across multi-session desktop activity.
          </p>
        </div>
        <button
          onClick={onRefreshDiscovery}
          disabled={discoveryLoading}
          className="flex items-center gap-2 px-3.5 py-2 text-xs font-semibold rounded-lg bg-white hover:bg-[#F8FAFC] border border-[#E2E8F0] text-[#0F172A] shadow-2xs transition active:scale-97 disabled:opacity-60 cursor-pointer self-start sm:self-auto"
        >
          <svg
            className={`w-3.5 h-3.5 ${discoveryLoading ? "animate-spin text-[#2563EB]" : "text-[#475569]"}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          <span>{discoveryLoading ? "Scanning…" : "Re-scan Patterns"}</span>
        </button>
      </div>

      {/* Discovery Error */}
      {discoveryError && (
        <div className="bg-rose-50 border border-rose-200 rounded-xl p-4 text-xs text-rose-700 flex items-start gap-2.5">
          <svg className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <div>
            <span className="font-semibold">Discovery API Error: </span>
            {discoveryError}
          </div>
        </div>
      )}

      {/* Discovered Workflow List */}
      {discoveryLoading ? (
        <div className="space-y-4">
          {[...Array(2)].map((_, i) => (
            <div key={i} className="bg-white border border-[#E2E8F0] rounded-xl p-6 space-y-4 animate-pulse">
              <div className="h-5 w-48 bg-[#F1F5F9] rounded" />
              <div className="h-4 w-96 bg-[#F1F5F9] rounded" />
              <div className="h-10 w-full bg-[#F1F5F9] rounded" />
            </div>
          ))}
        </div>
      ) : !discovery || !discovery.detected || discovery.workflows.length === 0 ? (
        <div className="bg-white border border-[#E2E8F0] rounded-xl p-12 text-center shadow-2xs">
          <div className="w-12 h-12 rounded-xl bg-[#EFF6FF] text-[#2563EB] flex items-center justify-center mx-auto mb-3">
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
          </div>
          <h3 className="text-base font-bold text-[#0F172A]">No Repeated Workflows Discovered Yet</h3>
          <p className="text-xs text-[#64748B] max-w-md mx-auto mt-1">
            WorkFlowOS scans across session histories for repeated sequences. Once multiple sessions perform the same ordered actions, candidate patterns appear here.
          </p>
          <div className="mt-4 flex items-center justify-center gap-3">
            <button
              onClick={onRefreshDiscovery}
              className="px-4 py-2 text-xs font-semibold rounded-lg bg-[#2563EB] hover:bg-[#1D4ED8] text-white shadow-2xs transition cursor-pointer"
            >
              Check Again
            </button>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          {discovery.workflows.map((wf, idx) => {
            const isApproved = approvals[wf.label] === "approved";
            const isRejected = approvals[wf.label] === "rejected";

            return (
              <div
                key={idx}
                className="bg-white border border-[#E2E8F0] rounded-xl p-6 shadow-2xs hover:shadow-xs transition flex flex-col justify-between gap-6"
              >
                <div>
                  {/* Top metadata row */}
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-3">
                    <div className="flex items-center gap-2.5">
                      {wf.rank !== undefined && (
                        <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded-full bg-slate-900 text-white shadow-2xs">
                          #{wf.rank}
                        </span>
                      )}
                      <h3 className="text-base font-bold text-[#0F172A] tracking-tight">
                        {wf.label || `Workflow Pattern #${idx + 1}`}
                      </h3>
                      {isApproved && (
                        <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
                          Approved
                        </span>
                      )}
                      {isRejected && (
                        <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 border border-slate-200">
                          Rejected
                        </span>
                      )}
                    </div>

                    <div className="flex items-center gap-2 text-xs font-mono">
                      {wf.ranking_score !== undefined && (
                        <span
                          title={wf.ranking_explanation || `Utility Score: ${Math.round(wf.ranking_score * 100)}/100`}
                          className={`px-2 py-0.5 rounded border text-[11px] font-semibold ${
                            wf.quality_tier === "exceptional"
                              ? "bg-purple-50 text-purple-700 border-purple-200"
                              : wf.quality_tier === "strong"
                              ? "bg-indigo-50 text-indigo-700 border-indigo-200"
                              : wf.quality_tier === "moderate"
                              ? "bg-slate-100 text-slate-700 border-slate-200"
                              : "bg-rose-50 text-rose-700 border-rose-200"
                          }`}
                        >
                          Score {Math.round(wf.ranking_score * 100)} ({wf.quality_tier || "standard"})
                        </span>
                      )}
                      {wf.confidence !== undefined && (
                        <span
                          title={wf.confidence_explanation || `Confidence: ${(wf.confidence * 100).toFixed(0)}%`}
                          className={`px-2 py-0.5 rounded border font-semibold ${
                            wf.confidence >= 0.8
                              ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                              : wf.confidence >= 0.65
                              ? "bg-amber-50 text-amber-700 border-amber-200"
                              : "bg-rose-50 text-rose-700 border-rose-200"
                          }`}
                        >
                          Confidence {(wf.confidence * 100).toFixed(0)}%
                        </span>
                      )}
                      <span className="px-2 py-0.5 rounded bg-blue-50 text-[#2563EB] border border-blue-200 font-semibold">
                        {wf.occurrences} repetitions
                      </span>
                      <span className="px-2 py-0.5 rounded bg-slate-100 text-[#475569] border border-[#E2E8F0]">
                        Similarity {(wf.similarity * 100).toFixed(0)}%
                      </span>
                      {wf.session_ids && (
                        <span className="text-[#94A3B8] hidden md:inline">
                          Across {wf.session_ids.length} sessions
                        </span>
                      )}
                    </div>
                  </div>

                  <p className="text-xs text-[#64748B] mb-4">
                    {wf.ranking_explanation || wf.confidence_explanation || `Observed sequence of ${wf.sequence.length} actions across multiple operational sessions.`}
                  </p>

                  {/* Connected Step Visualizer */}
                  <div className="bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl p-4 overflow-x-auto">
                    <div className="flex items-center gap-2 min-w-max">
                      {wf.sequence.map((step, sIdx) => {
                        return (
                          <React.Fragment key={sIdx}>
                            <div className="flex items-center gap-2 bg-white border border-[#E2E8F0] px-3 py-2 rounded-lg shadow-2xs">
                              <span className="w-5 h-5 rounded-full bg-[#EFF6FF] text-[#2563EB] font-bold text-[10px] flex items-center justify-center font-mono">
                                {sIdx + 1}
                              </span>
                              <div>
                                <div className="font-mono text-xs font-semibold text-[#0F172A]">
                                  {formatEventStep(step)}
                                </div>
                              </div>
                            </div>
                            {sIdx < wf.sequence.length - 1 && (
                              <svg
                                className="w-4 h-4 text-[#94A3B8] shrink-0"
                                fill="none"
                                viewBox="0 0 24 24"
                                stroke="currentColor"
                                strokeWidth={2}
                              >
                                <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                              </svg>
                            )}
                          </React.Fragment>
                        );
                      })}
                    </div>
                  </div>
                </div>

                {/* Bottom Action Footer */}
                <div className="flex items-center justify-between pt-4 border-t border-[#E2E8F0]">
                  <span className="text-xs text-[#64748B]">
                    Status: <strong className="text-[#0F172A]">{isApproved ? "Approved" : isRejected ? "Dismissed" : "Awaiting Review"}</strong>
                  </span>
                  <button
                    onClick={() => handleReview(wf)}
                    className="flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg bg-[#2563EB] hover:bg-[#1D4ED8] text-white shadow-2xs transition active:scale-97 cursor-pointer"
                  >
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                    <span>Review & Automate with AI</span>
                  </button>
                </div>
              </div>
            );
          })}

          {/* Suppressed / Filtered Patterns Accordion */}
          {discovery.suppressed_workflows && discovery.suppressed_workflows.length > 0 && (
            <details className="group bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl p-4 text-xs transition">
              <summary className="font-semibold text-[#475569] flex items-center justify-between cursor-pointer select-none">
                <div className="flex items-center gap-2">
                  <svg className="w-4 h-4 text-[#64748B] transition group-open:rotate-90" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                  </svg>
                  <span>Filtered Noise & Duplicates ({discovery.suppressed_workflows.length})</span>
                </div>
                <span className="text-[11px] font-normal text-[#94A3B8]">
                  Automatically pruned to reduce clutter and maintain canonical workflow representatives
                </span>
              </summary>
              <div className="mt-3 space-y-2 pt-3 border-t border-[#E2E8F0]">
                {discovery.suppressed_workflows.map((sw, sIdx) => (
                  <div key={sIdx} className="bg-white border border-[#E2E8F0] rounded-lg p-3 flex flex-col md:flex-row md:items-center justify-between gap-2 shadow-2xs">
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-semibold text-[#0F172A]">{sw.label}</span>
                        <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-amber-50 text-amber-700 border border-amber-200">
                          {sw.suppression_reason || "SUPPRESSED"}
                        </span>
                        {sw.representative_pattern_id && (
                          <span className="text-[10px] text-[#64748B]">
                            &rarr; Rep: <strong>{sw.representative_pattern_id}</strong>
                          </span>
                        )}
                      </div>
                      <div className="text-[11px] font-mono text-[#64748B]">
                        {sw.sequence.join(" \u2192 ")}
                      </div>
                    </div>
                    <div className="flex items-center gap-2 text-[11px] text-[#94A3B8] font-mono shrink-0">
                      <span>{sw.occurrences} sess</span>
                      <span>&bull;</span>
                      <span>Sim {Math.round(sw.similarity * 100)}%</span>
                    </div>
                  </div>
                ))}
              </div>
            </details>
          )}
        </div>
      )}

      {/* AI Proposal & Execution Modal */}
      {reviewWorkflow && (
        <div
          className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4 z-50 animate-fadeIn"
          onClick={closeModal}
        >
          <div
            className="bg-white border border-[#E2E8F0] rounded-2xl max-w-2xl w-full shadow-xl flex flex-col max-h-[90vh] overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="px-6 py-4.5 border-b border-[#E2E8F0] flex items-center justify-between shrink-0 bg-[#F8FAFC]">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-[#2563EB] bg-[#EFF6FF] px-2 py-0.5 rounded border border-[#BFDBFE]">
                    Gemini AI Proposal
                  </span>
                  <span className="text-xs text-[#64748B]">
                    {reviewWorkflow.occurrences} observed occurrences
                  </span>
                </div>
                <h3 className="text-base font-bold text-[#0F172A] mt-1">
                  {proposal?.name || reviewWorkflow.label || "Workflow Proposal"}
                </h3>
              </div>
              <button
                onClick={closeModal}
                className="text-[#94A3B8] hover:text-[#0F172A] p-1.5 rounded-lg hover:bg-[#E2E8F0] transition cursor-pointer"
              >
                ✕
              </button>
            </div>

            {/* Modal Body */}
            <div className="overflow-y-auto flex-1 px-6 py-5 space-y-5 text-xs">
              {aiLoading ? (
                <div className="py-12 flex flex-col items-center justify-center space-y-3">
                  <div className="w-8 h-8 border-3 border-[#2563EB] border-t-transparent rounded-full animate-spin" />
                  <p className="text-sm font-semibold text-[#0F172A]">Analyzing workflow with Gemini AI…</p>
                  <p className="text-xs text-[#64748B]">Synthesizing sequence into validated automation actions</p>
                </div>
              ) : aiError ? (
                <div className="bg-rose-50 border border-rose-200 rounded-xl p-4 text-xs text-rose-700">
                  <p className="font-semibold">AI Generation Failed</p>
                  <p className="mt-1 text-rose-600">{aiError}</p>
                </div>
              ) : (
                <>
                  {/* Rationale */}
                  {proposal?.description && (
                    <div className="bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl p-4">
                      <p className="font-semibold text-[#0F172A] mb-1">Automation Rationale</p>
                      <p className="text-[#475569] leading-relaxed">{proposal.description}</p>
                    </div>
                  )}

                  {/* Proposed Actions List */}
                  <div>
                    <h4 className="font-semibold text-[#0F172A] mb-2 uppercase tracking-wider text-[11px]">
                      Action Sequence ({proposal?.actions.length ?? 0} Steps)
                    </h4>
                    <div className="space-y-2">
                      {proposal?.actions.map((act, i) => (
                        <div
                          key={i}
                          className="flex items-center justify-between p-3 rounded-xl border border-[#E2E8F0] bg-white shadow-2xs"
                        >
                          <div className="flex items-center gap-3">
                            <span className="w-6 h-6 rounded-full bg-[#EFF6FF] text-[#2563EB] font-bold text-xs flex items-center justify-center font-mono shrink-0">
                              {i + 1}
                            </span>
                            <div>
                              <div className="font-mono font-semibold text-[#0F172A]">
                                {formatEventStep(act.type)}
                              </div>
                              {act.target && (
                                <div className="text-[11px] text-[#64748B] mt-0.5">
                                  Target: <span className="font-mono text-[#0F172A]">{act.target}</span>
                                </div>
                              )}
                            </div>
                          </div>
                          <span className={`text-[10px] font-medium px-2 py-0.5 rounded border shrink-0 ${getAppBadgeClass(act.application)}`}>
                            {getApplicationDisplayName(act.application)}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Execution Target Parameter */}
                  <div className="bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl p-4 space-y-2">
                    <label className="font-semibold text-[#0F172A] block">
                      Customer Parameter (CRM & Notification)
                    </label>
                    <div className="flex items-center gap-2">
                      <input
                        type="text"
                        value={testCustomer}
                        onChange={(e) => setTestCustomer(e.target.value)}
                        placeholder="Enter customer name…"
                        className="flex-1 bg-white border border-[#E2E8F0] rounded-lg px-3 py-1.5 text-xs text-[#0F172A] focus:outline-none focus:border-[#2563EB]"
                      />
                      <button
                        onClick={() => setTestCustomer("Rahul")}
                        className={`px-2.5 py-1.5 rounded-lg border text-xs font-medium cursor-pointer transition ${
                          testCustomer === "Rahul"
                            ? "bg-[#DBEAFE] border-[#BFDBFE] text-[#1D4ED8]"
                            : "bg-white border-[#E2E8F0] text-[#475569] hover:bg-[#F8FAFC]"
                        }`}
                      >
                        Rahul (Happy Path)
                      </button>
                      <button
                        onClick={() => setTestCustomer("UnknownUser")}
                        className={`px-2.5 py-1.5 rounded-lg border text-xs font-medium cursor-pointer transition ${
                          testCustomer === "UnknownUser"
                            ? "bg-[#DBEAFE] border-[#BFDBFE] text-[#1D4ED8]"
                            : "bg-white border-[#E2E8F0] text-[#475569] hover:bg-[#F8FAFC]"
                        }`}
                      >
                        Unknown (Pause Demo)
                      </button>
                    </div>
                  </div>

                  {/* Execution In Progress Banner */}
                  {isExecuting && (
                    <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 flex items-center gap-3">
                      <div className="w-5 h-5 border-2 border-[#2563EB] border-t-transparent rounded-full animate-spin shrink-0" />
                      <div>
                        <p className="text-xs font-semibold text-[#1D4ED8]">Executing Automation via Playwright…</p>
                        <p className="text-[11px] text-blue-700/80">Interacting with demo applications in real time</p>
                      </div>
                    </div>
                  )}

                  {/* Execution Error Banner */}
                  {executionError && (
                    <div className="bg-rose-50 border border-rose-200 rounded-xl p-3 text-xs text-rose-700">
                      <span className="font-semibold">Error: </span>
                      {executionError}
                    </div>
                  )}

                  {/* Execution Result Card */}
                  {executionResult && !isExecuting && (
                    <div
                      className={`rounded-xl p-4 border ${
                        executionResult.status === "completed"
                          ? "bg-emerald-50 border-emerald-200"
                          : executionResult.status === "paused"
                          ? "bg-amber-50 border-amber-200"
                          : executionResult.status === "cancelled"
                          ? "bg-slate-100 border-slate-200"
                          : "bg-rose-50 border-rose-200"
                      }`}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <p
                          className={`text-xs font-bold ${
                            executionResult.status === "completed"
                              ? "text-emerald-800"
                              : executionResult.status === "paused"
                              ? "text-amber-800"
                              : executionResult.status === "cancelled"
                              ? "text-slate-700"
                              : "text-rose-800"
                          }`}
                        >
                          {executionResult.status === "completed"
                            ? "✓ Automation Completed Successfully"
                            : executionResult.status === "paused"
                            ? "⏸ Paused — Human Intervention Required"
                            : executionResult.status === "cancelled"
                            ? "✕ Execution Cancelled"
                            : "⚠ Execution Failed"}
                        </p>
                        <span className="text-[10px] font-mono text-[#64748B]">
                          {executionResult.completed_actions.length}/{executionResult.total_actions} steps completed
                        </span>
                      </div>

                      {/* Human intervention details */}
                      {executionResult.human_intervention && (
                        <div className="bg-white/80 border border-amber-300 rounded-lg p-3 my-2 text-xs space-y-1">
                          <p className="font-semibold text-amber-900">{executionResult.human_intervention.title}</p>
                          <p className="text-amber-800">{executionResult.human_intervention.reason}</p>
                          <p className="text-amber-700 italic">{executionResult.human_intervention.action_required}</p>
                        </div>
                      )}

                      {/* Step Results List */}
                      {executionResult.all_actions && executionResult.all_actions.length > 0 && (
                        <div className="space-y-1.5 mt-3 pt-3 border-t border-[#E2E8F0]/60">
                          {executionResult.all_actions.map((a, i) => (
                            <div key={i} className="flex items-center gap-2 text-xs">
                              <span
                                className={`w-4 h-4 rounded-full flex items-center justify-center text-[10px] font-bold ${
                                  a.status === "completed"
                                    ? "bg-[#16A34A] text-white"
                                    : a.status === "failed"
                                    ? "bg-[#DC2626] text-white"
                                    : "bg-slate-200 text-slate-500"
                                }`}
                              >
                                {a.status === "completed" ? "✓" : a.status === "failed" ? "✗" : "○"}
                              </span>
                              <span className="font-mono text-[#0F172A] font-semibold">{a.action}</span>
                              {a.message && <span className="text-[#64748B]">— {a.message}</span>}
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Resume / Cancel Controls */}
                      {executionResult.status === "paused" && executionResult.resume_available && (
                        <div className="flex items-center gap-2.5 mt-4 pt-3 border-t border-amber-200">
                          <button
                            onClick={handleResume}
                            disabled={isResuming || isCancelling}
                            className="px-4 py-1.5 text-xs font-semibold rounded-lg bg-[#2563EB] hover:bg-[#1D4ED8] text-white shadow-2xs transition active:scale-97 disabled:opacity-60 cursor-pointer"
                          >
                            {isResuming ? "Resuming…" : "Resume Execution"}
                          </button>
                          <button
                            onClick={handleCancel}
                            disabled={isResuming || isCancelling}
                            className="px-3.5 py-1.5 text-xs font-semibold rounded-lg bg-white hover:bg-rose-50 text-[#DC2626] border border-rose-200 transition active:scale-97 disabled:opacity-60 cursor-pointer"
                          >
                            {isCancelling ? "Cancelling…" : "Cancel Workflow"}
                          </button>
                        </div>
                      )}
                    </div>
                  )}
                </>
              )}
            </div>

            {/* Modal Footer Controls */}
            {proposal && !aiLoading && !aiError && (
              <div className="px-6 py-4 border-t border-[#E2E8F0] shrink-0 flex items-center justify-between gap-3 bg-[#F8FAFC]">
                <div className="flex items-center gap-2 text-xs">
                  {approvalStatus === "approved" && (
                    <span className="text-emerald-700 font-semibold flex items-center gap-1">
                      ✓ Proposal Approved by Operator
                    </span>
                  )}
                  {approvalStatus === "rejected" && (
                    <span className="text-[#64748B]">Proposal Dismissed</span>
                  )}
                </div>

                <div className="flex items-center gap-2.5">
                  <button
                    onClick={() => {
                      setApprovalStatus("rejected");
                      if (reviewWorkflow) {
                        setApprovals((prev) => ({ ...prev, [reviewWorkflow.label]: "rejected" }));
                      }
                    }}
                    disabled={isExecuting || isResuming || approvalStatus !== "idle"}
                    className="px-3.5 py-2 text-xs font-medium rounded-lg bg-white hover:bg-[#F8FAFC] text-[#475569] border border-[#E2E8F0] transition disabled:opacity-50 cursor-pointer"
                  >
                    Reject
                  </button>
                  <button
                    onClick={handleApproveAndRun}
                    disabled={
                      isExecuting ||
                      approvalStatus === "rejected" ||
                      executionResult?.status === "completed"
                    }
                    className="px-4 py-2 text-xs font-semibold rounded-lg bg-[#2563EB] hover:bg-[#1D4ED8] text-white shadow-2xs transition active:scale-97 disabled:opacity-50 cursor-pointer"
                  >
                    {isExecuting
                      ? "Executing…"
                      : approvalStatus === "approved"
                      ? "Run Again"
                      : "Approve & Execute via Playwright"}
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
