"use client";

import React, { useState, useCallback } from "react";
import {
  DiscoveryResult,
  DiscoveredWorkflow,
  WorkflowProposal,
  AutomationExecutionResponse,
  ApprovalStatus,
  WorkflowLearningState,
} from "@/lib/types";
import {
  API_BASE_URL,
  formatEventStep,
  getAppBadgeClass,
  getApplicationDisplayName,
  formatApiErrorMessage,
  getWorkflowCanonicalId,
} from "@/lib/utils";

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
  const [editedProposal, setEditedProposal] = useState<WorkflowProposal | null>(null);
  const [isEditingWorkflow, setIsEditingWorkflow] = useState(false);
  const [showRejectInput, setShowRejectInput] = useState(false);
  const [rejectionReasonInput, setRejectionReasonInput] = useState("");
  const [learningState, setLearningState] = useState<WorkflowLearningState | null>(null);
  const [learningLoading, setLearningLoading] = useState(false);
  const [feedbackSuccessMsg, setFeedbackSuccessMsg] = useState<string | null>(null);
  const [feedbackErrorMsg, setFeedbackErrorMsg] = useState<string | null>(null);
  const [isSubmittingFeedback, setIsSubmittingFeedback] = useState(false);

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

  const fetchLearningState = useCallback(async (wf: DiscoveredWorkflow) => {
    setLearningLoading(true);
    const wfId = getWorkflowCanonicalId(wf.sequence, wf.workflow_id);
    try {
      const res = await fetch(`${API_BASE_URL}/api/workflows/${wfId}/learning`);
      if (res.ok) {
        const data = await res.json();
        setLearningState(data);
      }
    } catch {
      // Offline or error fallback
    } finally {
      setLearningLoading(false);
    }
  }, []);

  const handleReview = useCallback(
    async (wf: DiscoveredWorkflow) => {
      setReviewWorkflow(wf);
      setProposal(null);
      setEditedProposal(null);
      setIsEditingWorkflow(false);
      setShowRejectInput(false);
      setRejectionReasonInput("");
      setFeedbackSuccessMsg(null);
      setFeedbackErrorMsg(null);
      setAiLoading(true);
      setAiError(null);
      setExecutionResult(null);
      setExecutionError(null);
      setApprovalStatus(approvals[wf.label] || "idle");

      fetchLearningState(wf);

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
          setEditedProposal(JSON.parse(JSON.stringify(data.workflow)));
        } else {
          throw new Error(data.error || "No proposal returned");
        }
      } catch (e: unknown) {
        setAiError(e instanceof Error ? e.message : "AI analysis failed");
      } finally {
        setAiLoading(false);
      }
    },
    [approvals, fetchLearningState]
  );

  const submitFeedback = async (
    decision: "approve" | "reject" | "edit_approve",
    opts?: { rejection_reason?: string; edited_workflow?: WorkflowProposal | Record<string, unknown> }
  ) => {
    if (!reviewWorkflow) return;
    setIsSubmittingFeedback(true);
    setFeedbackSuccessMsg(null);
    setFeedbackErrorMsg(null);
    const wfId = getWorkflowCanonicalId(reviewWorkflow.sequence, reviewWorkflow.workflow_id);

    try {
      const res = await fetch(`${API_BASE_URL}/api/workflows/${wfId}/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          decision,
          rejection_reason: opts?.rejection_reason,
          edited_workflow: opts?.edited_workflow,
          original_workflow: proposal,
          session_id: reviewWorkflow.session_ids?.[0],
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => null);
        throw new Error(formatApiErrorMessage(err, `Server returned ${res.status}`));
      }
      const data = await res.json();
      if (data.learning_state) {
        setLearningState(data.learning_state);
      }

      if (decision === "approve") {
        setApprovalStatus("approved");
        setApprovals((prev) => ({ ...prev, [reviewWorkflow.label]: "approved" }));
        setFeedbackSuccessMsg("✓ Feedback recorded: Approved. Learning state updated.");
      } else if (decision === "reject") {
        setApprovalStatus("rejected");
        setApprovals((prev) => ({ ...prev, [reviewWorkflow.label]: "rejected" }));
        setShowRejectInput(false);
        setFeedbackSuccessMsg("✕ Feedback recorded: Rejected. Workflow deprioritized.");
      } else if (decision === "edit_approve") {
        setApprovalStatus("approved");
        setApprovals((prev) => ({ ...prev, [reviewWorkflow.label]: "approved" }));
        setIsEditingWorkflow(false);
        if (opts?.edited_workflow) {
          setProposal(opts.edited_workflow as WorkflowProposal);
        }
        setFeedbackSuccessMsg("✎ Feedback recorded: Edited & Approved.");
      }
      onRefreshDiscovery();
    } catch (e: unknown) {
      setFeedbackErrorMsg(e instanceof Error ? e.message : "Failed to record feedback");
    } finally {
      setIsSubmittingFeedback(false);
    }
  };

  const handleApproveAndRun = async () => {
    if (!proposal) return;
    setIsExecuting(true);
    setExecutionError(null);
    setExecutionResult(null);

    const activeWorkflow = editedProposal || proposal;
    const updatedActions = activeWorkflow.actions.map((act) =>
      act.type === "search_customer" || act.type === "update_customer"
        ? { ...act, target: testCustomer }
        : act
    );

    try {
      const res = await fetch(`${API_BASE_URL}/api/automation/execute`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          workflow: { ...activeWorkflow, actions: updatedActions },
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
          fetchLearningState(reviewWorkflow);
        }
        onExecutionComplete();
      } else if (data.status === "paused") {
        setApprovalStatus("approved");
        if (reviewWorkflow) {
          fetchLearningState(reviewWorkflow);
        }
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
                      {wf.recommendation_status && (
                        <span
                          className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider ${
                            wf.recommendation_status === "RECOMMENDED"
                              ? "bg-emerald-100 text-emerald-800 border border-emerald-300"
                              : wf.recommendation_status === "DEPRIORITIZED"
                              ? "bg-rose-100 text-rose-800 border border-rose-300"
                              : wf.recommendation_status === "LEARNING"
                              ? "bg-sky-100 text-sky-800 border border-sky-300"
                              : "bg-slate-100 text-slate-700 border border-slate-300"
                          }`}
                        >
                          {wf.recommendation_status}
                        </span>
                      )}
                    </div>

                    <div className="flex items-center gap-2 text-xs font-mono">
                      {wf.learning_score !== undefined && (
                        <span
                          title={wf.learning_explanation || `Adaptive Learning Score: ${wf.learning_score.toFixed(2)}`}
                          className="px-2 py-0.5 rounded border border-blue-200 bg-blue-50 text-blue-800 font-semibold text-[11px]"
                        >
                          Learning {wf.learning_score.toFixed(2)}
                        </span>
                      )}
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

                  {/* Phase 8.4 Explainability Accordion: "Why was this detected?" */}
                  <details className="group mt-3 border border-[#E2E8F0] rounded-xl bg-slate-50/60 p-3 text-xs transition">
                    <summary className="font-semibold text-[#334155] flex items-center justify-between cursor-pointer select-none">
                      <div className="flex items-center gap-2">
                        <svg
                          className="w-3.5 h-3.5 text-[#64748B] transition group-open:rotate-90"
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                          strokeWidth={2}
                        >
                          <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                        </svg>
                        <span>Why was this detected?</span>
                        <span className="text-[10px] font-mono font-normal px-1.5 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200">
                          Explainability Evidence
                        </span>
                      </div>
                      <span className="text-[11px] font-normal text-[#94A3B8]">
                        Deterministic alignment & ranking metrics
                      </span>
                    </summary>

                    <div className="mt-3 pt-3 border-t border-[#E2E8F0] space-y-3">
                      {/* Detection Criteria */}
                      <div>
                        <div className="font-semibold text-[#0F172A] mb-1 flex items-center gap-1.5">
                          <span className="w-1.5 h-1.5 rounded-full bg-blue-600"></span>
                          <span>Detection Criteria & Session Support</span>
                        </div>
                        <p className="text-[#475569] leading-relaxed">
                          {wf.explanation?.detection_reason || `Qualified based on ${wf.occurrences} observed sessions meeting the discovery threshold.`}
                        </p>
                        {wf.explanation?.supporting_sessions && wf.explanation.supporting_sessions.length > 0 && (
                          <div className="mt-2 flex flex-wrap items-center gap-1.5">
                            <span className="text-[11px] text-[#64748B]">Supporting sessions:</span>
                            {wf.explanation.supporting_sessions.map((s, idx) => (
                              <span key={idx} className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-white border border-[#CBD5E1] text-[#334155]">
                                {s}
                              </span>
                            ))}
                          </div>
                        )}
                        {/* Phase 8.5: Optional Steps Evidence */}
                        {wf.optional_steps && wf.optional_steps.length > 0 && (
                          <div className="mt-2 flex flex-wrap items-center gap-1.5">
                            <span className="text-[11px] font-medium text-amber-800">Optional steps detected:</span>
                            {wf.optional_steps.map((optStep, idx) => (
                              <span key={idx} className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-amber-50 border border-amber-200 text-amber-800">
                                {optStep}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>

                      {/* Alignment & Consistency Grid */}
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-2 pt-1">
                        <div className="bg-white border border-[#E2E8F0] rounded-lg p-2.5">
                          <div className="font-semibold text-[#0F172A] mb-1">Sequence Alignment Fidelity</div>
                          <p className="text-[#475569] mb-2">
                            {wf.explanation?.sequence_evidence?.variations_summary || `Average alignment similarity: ${Math.round(wf.similarity * 100)}%`}
                          </p>
                          <div className="flex flex-wrap gap-2 text-[10px] font-mono">
                            <span className="px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200">
                              {wf.explanation?.sequence_evidence?.exact_match_sessions_count ?? wf.occurrences} exact replays
                            </span>
                            {(wf.explanation?.sequence_evidence?.total_insertions_observed ?? 0) > 0 && (
                              <span className="px-1.5 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200">
                                {wf.explanation?.sequence_evidence?.total_insertions_observed} insertions tolerated
                              </span>
                            )}
                            {(wf.explanation?.sequence_evidence?.total_transpositions_observed ?? 0) > 0 && (
                              <span className="px-1.5 py-0.5 rounded bg-purple-50 text-purple-700 border border-purple-200">
                                {wf.explanation?.sequence_evidence?.total_transpositions_observed} step swaps tolerated
                              </span>
                            )}
                            {/* Phase 8.5: Partial Support Badge */}
                            {(wf.partial_support_count ?? 0) > 0 && (
                              <span className="px-1.5 py-0.5 rounded bg-teal-50 text-teal-700 border border-teal-200">
                                {wf.partial_support_count} partial execution(s)
                              </span>
                            )}
                            {/* Phase 8.5: Intra-Session Repetitions Badge */}
                            {(wf.intra_session_repetitions ?? 0) > 0 && (
                              <span className="px-1.5 py-0.5 rounded bg-cyan-50 text-cyan-700 border border-cyan-200">
                                +{wf.intra_session_repetitions} intra-session rep(s)
                              </span>
                            )}
                          </div>
                        </div>

                        <div className="bg-white border border-[#E2E8F0] rounded-lg p-2.5">
                          <div className="font-semibold text-[#0F172A] mb-1">Session Replay Consistency</div>
                          <p className="text-[#475569] mb-2">
                            {wf.explanation?.consistency_evidence?.consistency_description || `Consistency ratio: ${wf.explanation?.consistency_evidence?.exact_replay_percentage ?? 100}%`}
                          </p>
                          <div className="flex flex-wrap gap-2 text-[10px] font-mono">
                            <span className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-700 border border-slate-200">
                              {wf.explanation?.sequence_evidence?.action_diversity_ratio ? `Action Diversity: ${Math.round(wf.explanation.sequence_evidence.action_diversity_ratio * 100)}%` : "High Diversity"}
                            </span>
                            <span className="px-1.5 py-0.5 rounded bg-indigo-50 text-indigo-700 border border-indigo-200">
                              {wf.explanation?.quality_explanation?.split(":")[0] || `Quality: ${wf.quality_tier || "Standard"}`}
                            </span>
                          </div>
                        </div>
                      </div>

                      {/* Confidence & Ranking Factors */}
                      {(wf.explanation?.confidence_factors || wf.explanation?.ranking_factors) && (
                        <div className="bg-white border border-[#E2E8F0] rounded-lg p-2.5 space-y-2">
                          <div className="font-semibold text-[#0F172A]">Key Scoring Drivers & Limiting Factors</div>
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-[11px]">
                            {/* Strengths / Drivers */}
                            <div>
                              <span className="text-[#059669] font-medium block mb-1">Primary Positive Drivers:</span>
                              <ul className="list-disc list-inside space-y-0.5 text-[#334155]">
                                {wf.explanation?.confidence_factors?.primary_strengths?.map((str, idx) => (
                                  <li key={idx}>{str}</li>
                                ))}
                                {wf.explanation?.ranking_factors?.primary_drivers?.map((drv, idx) => (
                                  <li key={`r-${idx}`}>{drv}</li>
                                ))}
                              </ul>
                            </div>
                            {/* Limiting Factors */}
                            <div>
                              <span className="text-[#D97706] font-medium block mb-1">Limiting Factors / Trade-offs:</span>
                              {((wf.explanation?.confidence_factors?.limiting_factors?.length ?? 0) > 0 || (wf.explanation?.ranking_factors?.limiting_factors?.length ?? 0) > 0) ? (
                                <ul className="list-disc list-inside space-y-0.5 text-[#475569]">
                                  {wf.explanation?.confidence_factors?.limiting_factors?.map((lim, idx) => (
                                    <li key={idx}>{lim}</li>
                                  ))}
                                  {wf.explanation?.ranking_factors?.limiting_factors?.map((lim, idx) => (
                                    <li key={`r-${idx}`}>{lim}</li>
                                  ))}
                                </ul>
                              ) : (
                                <span className="text-[#64748B] italic">No significant limiting factors identified.</span>
                              )}
                            </div>
                          </div>
                        </div>
                      )}

                      {/* Representative Rationale if applicable */}
                      {wf.explanation?.representative_explanation && (
                        <div className="text-[11px] text-[#475569] bg-blue-50/50 border border-blue-100 rounded-lg p-2">
                          <strong className="text-blue-900">Representative Rationale:</strong> {wf.explanation.representative_explanation}
                        </div>
                      )}

                      {/* Limitations Disclaimer */}
                      {wf.explanation?.limitations && wf.explanation.limitations.length > 0 && (
                        <div className="text-[10px] text-[#64748B] border-t border-[#E2E8F0] pt-2 space-y-0.5">
                          {wf.explanation.limitations.map((limit, lIdx) => (
                            <div key={lIdx} className="flex items-start gap-1">
                              <span className="text-amber-500 font-bold">&bull;</span>
                              <span>{limit}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </details>
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
                      <div className="text-[11px] font-mono text-[#64748B] mb-1">
                        {sw.sequence.join(" \u2192 ")}
                      </div>
                      {sw.explanation?.suppression_explanation && (
                        <p className="text-[11px] text-[#475569] mt-1 leading-snug">
                          {sw.explanation.suppression_explanation}
                        </p>
                      )}
                      {sw.explanation?.suppression_evidence?.measured_value && (
                        <div className="mt-1 flex items-center gap-2 text-[10px] text-[#64748B] font-mono">
                          <span>Measured: <strong className="text-[#334155]">{sw.explanation.suppression_evidence.measured_value}</strong></span>
                          {sw.explanation.suppression_evidence.threshold_criterion && (
                            <>
                              <span>&bull;</span>
                              <span>Criterion: {sw.explanation.suppression_evidence.threshold_criterion}</span>
                            </>
                          )}
                        </div>
                      )}
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

                  {/* Phase 9: Adaptive Learning & Recommendation Telemetry */}
                  <div className="bg-white border border-[#E2E8F0] rounded-xl p-4 shadow-2xs space-y-3">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-[#E2E8F0] pb-2.5">
                      <div className="flex items-center gap-2">
                        <span className="w-2.5 h-2.5 rounded-full bg-[#2563EB]" />
                        <h4 className="text-xs font-bold text-[#0F172A] tracking-tight uppercase">
                          Learning Status & Adaptive Recommendation
                        </h4>
                        {learningLoading && (
                          <span className="text-[10px] text-blue-600 animate-pulse font-mono font-medium">Syncing…</span>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-[11px] font-mono text-[#64748B]">Recommendation:</span>
                        <span
                          className={`px-2.5 py-0.5 rounded-full text-xs font-bold uppercase tracking-wider ${
                            (learningState?.recommendation_status || reviewWorkflow?.recommendation_status) === "RECOMMENDED"
                              ? "bg-emerald-100 text-emerald-800 border border-emerald-300"
                              : (learningState?.recommendation_status || reviewWorkflow?.recommendation_status) === "DEPRIORITIZED"
                              ? "bg-rose-100 text-rose-800 border border-rose-300"
                              : (learningState?.recommendation_status || reviewWorkflow?.recommendation_status) === "LEARNING"
                              ? "bg-sky-100 text-sky-800 border border-sky-300"
                              : "bg-slate-100 text-slate-700 border border-slate-300"
                          }`}
                        >
                          {learningState?.recommendation_status || reviewWorkflow?.recommendation_status || "NEW"}
                        </span>
                      </div>
                    </div>

                    {/* Telemetry Metrics Grid */}
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 pt-1 text-xs">
                      {/* Learning Score */}
                      <div className="bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg p-2.5">
                        <div className="text-[10px] uppercase font-semibold text-[#64748B]">Learning Score</div>
                        <div className="text-lg font-bold font-mono text-[#0F172A] mt-0.5">
                          {(learningState?.learning_score ?? reviewWorkflow?.learning_score ?? 0.50).toFixed(2)}
                        </div>
                        <div className="w-full bg-slate-200 h-1.5 rounded-full mt-1.5 overflow-hidden">
                          <div
                            className="bg-[#2563EB] h-full rounded-full transition-all duration-300"
                            style={{
                              width: `${Math.round(
                                (learningState?.learning_score ?? reviewWorkflow?.learning_score ?? 0.50) * 100
                              )}%`,
                            }}
                          />
                        </div>
                      </div>

                      {/* Human Feedback */}
                      <div className="bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg p-2.5">
                        <div className="text-[10px] uppercase font-semibold text-[#64748B]">Feedback History</div>
                        <div className="flex flex-col gap-0.5 mt-1 font-mono text-[11px]">
                          <span className="text-emerald-700 font-medium">✓ Approved: {learningState?.approval_count ?? 0}</span>
                          <span className="text-rose-700 font-medium">✕ Rejected: {learningState?.rejection_count ?? 0}</span>
                          <span className="text-indigo-700 font-medium">✎ Edited: {learningState?.edit_count ?? 0}</span>
                        </div>
                      </div>

                      {/* Execution Telemetry */}
                      <div className="bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg p-2.5">
                        <div className="text-[10px] uppercase font-semibold text-[#64748B]">Execution History</div>
                        <div className="flex flex-col gap-0.5 mt-1 font-mono text-[11px]">
                          <span className="text-emerald-700 font-medium">
                            ✓ Successful: {learningState?.successful_execution_count ?? 0}
                          </span>
                          <span className="text-rose-700 font-medium">
                            ✕ Failed: {learningState?.failed_execution_count ?? 0}
                          </span>
                          <span className="text-[#64748B]">Total Runs: {learningState?.execution_count ?? 0}</span>
                        </div>
                      </div>

                      {/* Interventions & Recoveries */}
                      <div className="bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg p-2.5">
                        <div className="text-[10px] uppercase font-semibold text-[#64748B]">Reliability Signals</div>
                        <div className="flex flex-col gap-0.5 mt-1 font-mono text-[11px]">
                          <span className="text-amber-700 font-medium">
                            Interventions: {learningState?.intervention_count ?? 0}
                          </span>
                          <span className="text-blue-700 font-medium">
                            Recoveries: {learningState?.recovery_count ?? 0}
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Explanation */}
                    <div className="bg-[#F1F5F9] border border-[#E2E8F0] rounded-lg p-2.5 text-xs text-[#334155] italic">
                      {learningState?.learning_explanation ||
                        reviewWorkflow?.learning_explanation ||
                        "New workflow candidate with no prior feedback or execution history."}
                    </div>

                    {/* Inline Feedback Controls */}
                    <div className="border-t border-[#E2E8F0] pt-3 flex flex-wrap items-center justify-between gap-2">
                      <div className="text-xs font-semibold text-[#475569]">
                        Submit Human Review Feedback:
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => submitFeedback("approve")}
                          disabled={isSubmittingFeedback || isExecuting}
                          className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-100 transition active:scale-97 cursor-pointer disabled:opacity-50"
                        >
                          ✓ Approve
                        </button>
                        <button
                          onClick={() => {
                            setShowRejectInput((prev) => !prev);
                            setIsEditingWorkflow(false);
                          }}
                          disabled={isSubmittingFeedback || isExecuting}
                          className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-rose-50 text-rose-700 border border-rose-200 hover:bg-rose-100 transition active:scale-97 cursor-pointer disabled:opacity-50"
                        >
                          ✕ Reject
                        </button>
                        <button
                          onClick={() => {
                            setIsEditingWorkflow((prev) => !prev);
                            setShowRejectInput(false);
                          }}
                          disabled={isSubmittingFeedback || isExecuting}
                          className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-indigo-50 text-indigo-700 border border-indigo-200 hover:bg-indigo-100 transition active:scale-97 cursor-pointer disabled:opacity-50"
                        >
                          ✎ Edit & Approve
                        </button>
                      </div>
                    </div>

                    {/* Small Rejection Reason Input Card */}
                    {showRejectInput && (
                      <div className="bg-rose-50/60 border border-rose-200 rounded-lg p-3 space-y-2 text-xs">
                        <label className="font-semibold text-rose-900 block">
                          Reason for Rejection (Optional):
                        </label>
                        <div className="flex items-center gap-2">
                          <input
                            type="text"
                            value={rejectionReasonInput}
                            onChange={(e) => setRejectionReasonInput(e.target.value)}
                            placeholder="e.g. Unnecessary automation, wrong steps, CRM duplicate..."
                            className="flex-1 bg-white border border-rose-300 rounded px-2.5 py-1.5 text-xs text-[#0F172A] focus:outline-none focus:border-rose-500"
                          />
                          <button
                            onClick={() => submitFeedback("reject", { rejection_reason: rejectionReasonInput })}
                            disabled={isSubmittingFeedback}
                            className="px-3 py-1.5 text-xs font-semibold rounded bg-rose-600 hover:bg-rose-700 text-white transition cursor-pointer disabled:opacity-50"
                          >
                            {isSubmittingFeedback ? "Submitting…" : "Confirm Rejection"}
                          </button>
                          <button
                            onClick={() => setShowRejectInput(false)}
                            className="px-2.5 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-100 rounded transition cursor-pointer"
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    )}

                    {/* Edit & Approve Editor Card */}
                    {isEditingWorkflow && editedProposal && (
                      <div className="bg-indigo-50/60 border border-indigo-200 rounded-lg p-3 space-y-2 text-xs">
                        <div className="font-semibold text-indigo-900">
                          Edit Workflow Proposal Before Approval:
                        </div>
                        <div className="space-y-2">
                          <div>
                            <span className="text-[11px] text-slate-600 block">Workflow Name:</span>
                            <input
                              type="text"
                              value={editedProposal.name}
                              onChange={(e) => setEditedProposal({ ...editedProposal, name: e.target.value })}
                              className="w-full bg-white border border-indigo-200 rounded px-2 py-1 text-xs text-[#0F172A]"
                            />
                          </div>
                          <div>
                            <span className="text-[11px] text-slate-600 block">Workflow Intent:</span>
                            <input
                              type="text"
                              value={editedProposal.intent}
                              onChange={(e) => setEditedProposal({ ...editedProposal, intent: e.target.value })}
                              className="w-full bg-white border border-indigo-200 rounded px-2 py-1 text-xs text-[#0F172A]"
                            />
                          </div>
                        </div>
                        <div className="flex items-center justify-end gap-2 pt-1">
                          <button
                            onClick={() => setIsEditingWorkflow(false)}
                            className="px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-100 rounded transition cursor-pointer"
                          >
                            Cancel
                          </button>
                          <button
                            onClick={() => submitFeedback("edit_approve", { edited_workflow: editedProposal })}
                            disabled={isSubmittingFeedback}
                            className="px-3 py-1 text-xs font-semibold rounded bg-indigo-600 hover:bg-indigo-700 text-white transition cursor-pointer disabled:opacity-50"
                          >
                            {isSubmittingFeedback ? "Saving…" : "Save & Approve"}
                          </button>
                        </div>
                      </div>
                    )}

                    {/* Feedback Status Alerts */}
                    {feedbackSuccessMsg && (
                      <div className="bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs px-3 py-2 rounded-lg flex items-center justify-between">
                        <span>{feedbackSuccessMsg}</span>
                        <button
                          onClick={() => setFeedbackSuccessMsg(null)}
                          className="text-emerald-700 hover:text-emerald-900 font-bold ml-2 cursor-pointer"
                        >
                          ✕
                        </button>
                      </div>
                    )}
                    {feedbackErrorMsg && (
                      <div className="bg-rose-50 border border-rose-200 text-rose-800 text-xs px-3 py-2 rounded-lg flex items-center justify-between">
                        <span>{feedbackErrorMsg}</span>
                        <button
                          onClick={() => setFeedbackErrorMsg(null)}
                          className="text-rose-700 hover:text-rose-900 font-bold ml-2 cursor-pointer"
                        >
                          ✕
                        </button>
                      </div>
                    )}
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
                      submitFeedback("reject", { rejection_reason: "Dismissed in operator review" });
                    }}
                    disabled={isExecuting || isResuming || isSubmittingFeedback || approvalStatus === "rejected"}
                    className="px-3.5 py-2 text-xs font-medium rounded-lg bg-white hover:bg-[#F8FAFC] text-[#475569] border border-[#E2E8F0] transition disabled:opacity-50 cursor-pointer"
                  >
                    Reject
                  </button>
                  <button
                    onClick={() => submitFeedback("approve")}
                    disabled={isExecuting || isResuming || isSubmittingFeedback || approvalStatus === "approved"}
                    className="px-3.5 py-2 text-xs font-medium rounded-lg bg-white hover:bg-emerald-50 text-emerald-700 border border-emerald-200 transition disabled:opacity-50 cursor-pointer"
                  >
                    Approve Feedback
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
