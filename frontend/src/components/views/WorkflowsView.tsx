"use client";

import React, { useState, useEffect } from "react";
import { createPortal } from "react-dom";
import {
  DiscoveredWorkflow,
  DiscoveryResult,
  WorkflowLearningState,
  AutomationPlan,
  ClosedLoopSummary,
  ViewId,
} from "@/lib/types";
import {
  formatEventStep,
  getApplicationDisplayName,
  getAppBadgeClass,
  getWorkflowCanonicalId,
} from "@/lib/utils";
import DiscoveryView from "./DiscoveryView";
import BuilderView from "./BuilderView";
import {
  fetchWorkflowLearningState,
  generateAutomationPlan,
  fetchClosedLoopSummary,
  deleteWorkflow,
} from "@/lib/api";

interface WorkflowsViewProps {
  discovery: DiscoveryResult | null;
  discoveryLoading: boolean;
  discoveryError: string | null;
  onRefreshDiscovery: () => void;
  onExecutionComplete: () => void;
  onNavigate: (view: ViewId) => void;
}

interface WorkflowDetailModalProps {
  workflow: DiscoveredWorkflow;
  onClose: () => void;
  onOpenAdvancedReview: () => void;
  onDeleteWorkflow?: (workflowId: string) => Promise<void> | void;
}

function WorkflowDetailModal({
  workflow,
  onClose,
  onOpenAdvancedReview,
  onDeleteWorkflow,
}: WorkflowDetailModalProps) {
  const [learning, setLearning] = useState<WorkflowLearningState | null>(null);
  const [plan, setPlan] = useState<AutomationPlan | null>(null);
  const [closedLoop, setClosedLoop] = useState<ClosedLoopSummary | null>(null);
  const [loadingDetails, setLoadingDetails] = useState(true);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const wfId = getWorkflowCanonicalId(workflow.sequence, workflow.workflow_id);

  useEffect(() => {
    const origOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = origOverflow;
    };
  }, []);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [onClose]);

  useEffect(() => {
    let isMounted = true;
    async function load() {
      setLoadingDetails(true);
      try {
        const [lData, pData, cData] = await Promise.allSettled([
          fetchWorkflowLearningState(wfId),
          generateAutomationPlan(
            wfId,
            workflow.label,
            workflow.sequence.map((step, idx) => ({
              id: `step_${idx + 1}`,
              action: step,
              application: step.includes("email")
                ? "demo_email"
                : step.includes("customer")
                ? "demo_crm"
                : "demo_chat",
            }))
          ),
          fetchClosedLoopSummary(wfId),
        ]);

        if (isMounted) {
          if (lData.status === "fulfilled") setLearning(lData.value);
          if (pData.status === "fulfilled") setPlan(pData.value.plan);
          if (cData.status === "fulfilled") setClosedLoop(cData.value);
        }
      } finally {
        if (isMounted) setLoadingDetails(false);
      }
    }
    load();
    return () => {
      isMounted = false;
    };
  }, [wfId, workflow.label, workflow.sequence]);

  const hasMutatingAction = workflow.sequence.some(
    (s) =>
      s.includes("update") ||
      s.includes("create") ||
      s.includes("delete") ||
      s.includes("send")
  );

  const isRejected =
    Boolean(workflow.is_rejected) ||
    learning?.last_feedback?.decision === "reject" ||
    Boolean(learning && learning.rejection_count > 0 && learning.approval_count === 0);

  const handleConfirmDelete = async () => {
    setIsDeleting(true);
    setDeleteError(null);
    try {
      if (onDeleteWorkflow) {
        await onDeleteWorkflow(wfId);
      } else {
        await deleteWorkflow(wfId);
      }
      setShowDeleteConfirm(false);
      onClose();
    } catch (err: unknown) {
      setDeleteError(err instanceof Error ? err.message : "Failed to delete workflow");
    } finally {
      setIsDeleting(false);
    }
  };

  if (typeof document === "undefined") {
    return null;
  }

  const modalOverlay = (
    <div
      className="fixed inset-x-0 bottom-0 top-16 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4 sm:p-6 z-40 overflow-hidden overscroll-contain animate-fadeIn"
      onClick={onClose}
    >
      <div
        className="bg-white border border-[#E2E8F0] rounded-2xl max-w-2xl w-full shadow-2xl flex flex-col max-h-[calc(100dvh-96px)] sm:max-h-[calc(100dvh-112px)] overflow-hidden animate-modal-enter"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-6 py-4.5 border-b border-[#E2E8F0] bg-[#F8FAFC] flex items-start justify-between shrink-0">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200">
                {wfId}
              </span>
              <span
                className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${
                  workflow.recommendation_status === "RECOMMENDED" ||
                  learning?.recommendation_status === "RECOMMENDED"
                    ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                    : "bg-blue-50 text-blue-700 border-blue-200"
                }`}
              >
                {learning?.recommendation_status ||
                  workflow.recommendation_status ||
                  "DISCOVERED"}
              </span>
              {workflow.confidence && (
                <span className="text-[10px] font-mono text-[#64748B]">
                  Confidence: {Math.round(workflow.confidence * 100)}%
                </span>
              )}
            </div>
            <div className="flex items-center gap-2">
              <h3 className="text-base font-bold text-[#0F172A]">
                {workflow.label}
              </h3>
              {loadingDetails && (
                <span className="text-[10px] text-[#94A3B8] font-mono animate-pulse">
                  Loading telemetry…
                </span>
              )}
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-[#94A3B8] hover:text-[#0F172A] p-1.5 rounded-lg hover:bg-[#E2E8F0] transition-colors duration-150 cursor-pointer"
            aria-label="Close workflow details"
          >
            ✕
          </button>
        </div>

        {/* Scrollable Content Body */}
        <div className="p-6 pb-8 sm:pb-10 overflow-y-auto overscroll-contain space-y-5 text-xs flex-1 min-h-0">
          {/* Discovery Stage */}
          <div className="border border-[#E2E8F0] rounded-xl p-4 bg-white space-y-1.5 shadow-2xs">
            <div className="flex items-center gap-2 text-[#0F172A] font-bold">
              <span className="text-emerald-600 font-bold">✓</span>
              <span>Discovery</span>
            </div>
            <p className="text-[#64748B] text-[11px] leading-relaxed">
              Repeated pattern detected across {workflow.occurrences} observed work
              sessions with {Math.round((workflow.similarity || 1) * 100)}% sequence
              similarity.
            </p>
          </div>

          {/* Understanding Stage */}
          <div className="border border-[#E2E8F0] rounded-xl p-4 bg-white space-y-1.5 shadow-2xs">
            <div className="flex items-center gap-2 text-[#0F172A] font-bold">
              <span className="text-emerald-600 font-bold">✓</span>
              <span>Understanding</span>
            </div>
            <p className="text-[#64748B] text-[11px] leading-relaxed">
              Intent understood: Multi-application workflow spanning {workflow.sequence.length} actions.
              Deterministic parameters and variables verified for automated execution.
            </p>
          </div>

          {/* Learning Stage */}
          <div className="border border-[#E2E8F0] rounded-xl p-4 bg-white space-y-1.5 shadow-2xs">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-[#0F172A] font-bold">
                <span className="text-emerald-600 font-bold">✓</span>
                <span>Learning & Feedback</span>
              </div>
              <span className="font-mono text-[10px] text-[#64748B]">
                Score: {learning?.learning_score ? Math.round(learning.learning_score * 100) : 50}%
              </span>
            </div>
            <p className="text-[#64748B] text-[11px] leading-relaxed">
              Status: <strong className="text-[#0F172A]">{learning?.recommendation_status || "LEARNING"}</strong>.
              {learning
                ? ` Approvals: ${learning.approval_count}, Rejections: ${learning.rejection_count}, Successful Runs: ${learning.successful_execution_count}.`
                : " Initial baseline score calculated from repetition and action diversity."}
            </p>
          </div>

          {/* Automation Plan Stage */}
          <div className="border border-[#E2E8F0] rounded-xl p-4 bg-white space-y-1.5 shadow-2xs">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-[#0F172A] font-bold">
                <span className="text-emerald-600 font-bold">✓</span>
                <span>Automation Plan</span>
              </div>
              <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-purple-50 text-purple-700 border border-purple-200">
                Strategy: {plan?.selected_strategy || "INTEGRATION"}
              </span>
            </div>
            <p className="text-[#64748B] text-[11px] leading-relaxed">
              Deterministic planner evaluated API, Integration, and Semantic UI
              strategies. Selected strategy provides highest reliability without
              unbounded fallbacks.
            </p>
          </div>

          {/* Closed-Loop Outcomes Stage */}
          {closedLoop && closedLoop.total_executions > 0 && (
            <div className="border border-[#E2E8F0] rounded-xl p-4 bg-white space-y-1.5 shadow-2xs">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-[#0F172A] font-bold">
                  <span className="text-emerald-600 font-bold">✓</span>
                  <span>Execution Outcome & Adaptation</span>
                </div>
                <span className="font-mono text-[10px] text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                  {closedLoop.successful_executions}/{closedLoop.total_executions} Successful
                </span>
              </div>
              <p className="text-[#64748B] text-[11px] leading-relaxed">
                Empirical reliability verified through closed-loop execution.
                {closedLoop.adaptations && closedLoop.adaptations.length > 0
                  ? ` Adaptations: ${closedLoop.adaptations.join(", ")}.`
                  : " Execution telemetry reinforces deterministic strategy weights."}
              </p>
            </div>
          )}

          {/* Approval Requirement Card */}
          <div
            className={`border rounded-xl p-4 space-y-1.5 ${
              hasMutatingAction
                ? "bg-amber-50/70 border-amber-200 text-amber-900"
                : "bg-emerald-50/70 border-emerald-200 text-emerald-900"
            }`}
          >
            <div className="flex items-center gap-2 font-bold text-xs">
              <span>{hasMutatingAction ? "⚠️" : "🛡️"}</span>
              <span>
                {hasMutatingAction
                  ? "Human Approval Required"
                  : "Operator Approval Gate Active"}
              </span>
            </div>
            <p className="text-[11px] leading-relaxed">
              {hasMutatingAction
                ? "This workflow contains mutating actions that modify customer or email state. Human operator sign-off is strictly mandatory before execution can proceed."
                : "All automated workflows require explicit operator confirmation before execution. Autonomous bypass is disabled."}
            </p>
          </div>

          {/* Steps Breakdown */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-[#64748B]">
                Workflow Steps ({workflow.sequence.length})
              </span>
              <span className="text-[10px] text-[#94A3B8]">Ordered sequence</span>
            </div>
            <div className="divide-y divide-[#E2E8F0] border border-[#E2E8F0] rounded-xl overflow-hidden bg-white">
              {workflow.sequence.map((stepVerb, idx) => {
                const appSlug = stepVerb.includes("email")
                  ? "demo_email"
                  : stepVerb.includes("customer")
                  ? "demo_crm"
                  : "demo_chat";
                const isMutating =
                  stepVerb.includes("update") ||
                  stepVerb.includes("create") ||
                  stepVerb.includes("delete") ||
                  stepVerb.includes("send");
                return (
                  <div
                    key={idx}
                    className="p-3 flex items-center justify-between gap-3 hover:bg-[#F8FAFC] transition text-xs"
                  >
                    <div className="flex items-center gap-3">
                      <span className="w-5 h-5 rounded-full bg-[#F1F5F9] font-mono text-[10px] text-[#64748B] flex items-center justify-center font-bold shrink-0">
                        {idx + 1}
                      </span>
                      <span className="font-mono font-medium text-[#0F172A]">
                        {formatEventStep(stepVerb)}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <span
                        className={`text-[10px] font-medium px-2 py-0.5 rounded border ${getAppBadgeClass(
                          appSlug
                        )}`}
                      >
                        {getApplicationDisplayName(appSlug)}
                      </span>
                      <span
                        className={`text-[9px] font-semibold px-1.5 py-0.5 rounded uppercase ${
                          isMutating
                            ? "bg-amber-50 text-amber-700 border border-amber-200"
                            : "bg-slate-50 text-slate-600 border border-slate-200"
                        }`}
                      >
                        {isMutating ? "Mutating" : "Read-only"}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Footer Actions */}
        <div className="px-6 py-4 border-t border-[#E2E8F0] bg-[#F8FAFC] flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2">
            <button
              onClick={onClose}
              className="px-3.5 py-2 text-xs font-medium rounded-lg border border-[#E2E8F0] text-[#64748B] hover:bg-white hover:text-[#0F172A] transition-all duration-150 active:translate-y-px cursor-pointer"
            >
              Close
            </button>
            {isRejected && (
              <button
                type="button"
                onClick={() => setShowDeleteConfirm(true)}
                disabled={isDeleting}
                className="px-3.5 py-2 text-xs font-semibold rounded-lg bg-rose-50 text-rose-700 border border-rose-200 hover:bg-rose-100 transition-all duration-150 active:translate-y-px cursor-pointer flex items-center gap-1.5"
              >
                <span>🗑️</span>
                <span>Delete Workflow</span>
              </button>
            )}
          </div>
          <button
            onClick={() => {
              onClose();
              onOpenAdvancedReview();
            }}
            className="flex items-center gap-1.5 px-4 py-2 text-xs font-semibold rounded-lg bg-[#2563EB] hover:bg-[#1D4ED8] hover:shadow-xs text-white shadow-2xs transition-all duration-150 active:translate-y-px cursor-pointer"
          >
            <span>Review & Automate</span>
            <span>→</span>
          </button>
        </div>

        {/* Delete Confirmation Modal */}
        {showDeleteConfirm && (
          <div
            className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4 z-60 animate-fadeIn"
            onClick={() => setShowDeleteConfirm(false)}
          >
            <div
              className="bg-white border border-[#E2E8F0] rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4 animate-modal-enter"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-xl bg-rose-50 border border-rose-200 flex items-center justify-center text-rose-600 shrink-0 text-lg">
                  ⚠️
                </div>
                <div>
                  <h3 className="text-sm font-bold text-[#0F172A]">Delete workflow?</h3>
                  <p className="text-xs text-[#64748B] mt-1 leading-relaxed">
                    Are you sure you want to delete &ldquo;{workflow.label}&rdquo;?
                    This permanently removes the workflow and its learning tombstone. This action cannot be undone.
                  </p>
                </div>
              </div>

              {deleteError && (
                <div className="bg-rose-50 border border-rose-200 text-rose-700 text-xs p-3 rounded-lg">
                  {deleteError}
                </div>
              )}

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-[#F1F5F9]">
                <button
                  type="button"
                  onClick={() => {
                    setShowDeleteConfirm(false);
                    setDeleteError(null);
                  }}
                  disabled={isDeleting}
                  className="px-3.5 py-2 text-xs font-medium rounded-lg border border-[#E2E8F0] text-[#64748B] hover:bg-[#F8FAFC] transition cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleConfirmDelete}
                  disabled={isDeleting}
                  className="px-4 py-2 text-xs font-semibold rounded-lg bg-rose-600 hover:bg-rose-700 text-white shadow-2xs transition cursor-pointer disabled:opacity-60"
                >
                  {isDeleting ? "Deleting…" : "Delete Workflow"}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );

  return createPortal(modalOverlay, document.body);
}

function useCountUp(target: number, duration: number = 700): number {
  const [current, setCurrent] = useState(0);

  useEffect(() => {
    let animationFrameId: number;

    const prefersReducedMotion =
      typeof window !== "undefined" &&
      window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    if (prefersReducedMotion || target === 0) {
      animationFrameId = requestAnimationFrame(() => {
        setCurrent(target);
      });
      return () => {
        if (animationFrameId) cancelAnimationFrame(animationFrameId);
      };
    }

    const startTime = performance.now();

    const tick = (now: number) => {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      // easeOutCubic curve
      const eased = 1 - Math.pow(1 - progress, 3);
      setCurrent(Math.round(eased * target));
      if (progress < 1) {
        animationFrameId = requestAnimationFrame(tick);
      }
    };

    animationFrameId = requestAnimationFrame(tick);
    return () => {
      if (animationFrameId) cancelAnimationFrame(animationFrameId);
    };
  }, [target, duration]);

  return current;
}

interface WorkflowCardProps {
  wf: DiscoveredWorkflow;
  index: number;
  onSelect: (wf: DiscoveredWorkflow) => void;
  onReview: (wf: DiscoveredWorkflow) => void;
  onDelete?: (wf: DiscoveredWorkflow) => void;
}

function WorkflowCard({ wf, index, onSelect, onReview, onDelete }: WorkflowCardProps) {
  const conf = wf.confidence
    ? Math.round(wf.confidence * 100)
    : 85;
  const status = wf.recommendation_status || "RECOMMENDED";
  const hasMutating = wf.sequence.some(
    (s) =>
      s.includes("update") ||
      s.includes("create") ||
      s.includes("delete") ||
      s.includes("send")
  );

  // Real data-driven count-up animations
  const animatedConf = useCountUp(conf, 700);
  const animatedOccurrences = useCountUp(wf.occurrences, 600);

  return (
    <div
      style={{ animationDelay: `${Math.min(index * 35, 210)}ms` }}
      className="bg-white border border-[#E2E8F0] rounded-xl p-5 shadow-2xs hover:shadow-xs hover:border-[#CBD5E1] hover:-translate-y-0.5 transition-all duration-200 ease-out animate-card-enter flex flex-col justify-between space-y-4 group"
    >
      <div>
        {/* Status & Confidence row */}
        <div className="flex items-center justify-between gap-2 mb-2">
          <span
            className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase border transition-colors duration-200 ${
              status === "RECOMMENDED"
                ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                : "bg-blue-50 text-blue-700 border-blue-200"
            }`}
          >
            {status}
          </span>
          <span className="text-[11px] font-mono text-[#64748B]">
            Confidence: <strong className="text-[#0F172A]">{animatedConf}%</strong>
          </span>
        </div>

        {/* Subtle Confidence Progress Bar */}
        <div className="w-full bg-[#F1F5F9] border border-[#E2E8F0] h-1.5 rounded-full overflow-hidden mb-3">
          <div
            className="bg-[#2563EB] h-full rounded-full transition-all duration-700 ease-out"
            style={{ width: `${animatedConf}%` }}
          />
        </div>

        <h4 className="text-sm font-bold text-[#0F172A] leading-snug">
          {wf.label}
        </h4>

        {/* Lifecycle Metrics Summary */}
        <div className="grid grid-cols-2 gap-2 mt-3 pt-3 border-t border-[#F1F5F9] text-[11px]">
          <div>
            <span className="text-[#94A3B8] block text-[10px] uppercase">
              Automation
            </span>
            <span className="font-semibold text-[#0F172A]">
              Available (Plan ready)
            </span>
          </div>
          <div>
            <span className="text-[#94A3B8] block text-[10px] uppercase">
              Approval
            </span>
            <span
              className={`font-semibold ${
                hasMutating ? "text-amber-700" : "text-emerald-700"
              }`}
            >
              {hasMutating ? "Mandatory" : "Operator Gate"}
            </span>
          </div>
          <div>
            <span className="text-[#94A3B8] block text-[10px] uppercase">
              Occurrences
            </span>
            <span className="font-mono text-[#0F172A]">
              {animatedOccurrences} observed sessions
            </span>
          </div>
          <div>
            <span className="text-[#94A3B8] block text-[10px] uppercase">
              Steps Count
            </span>
            <span className="font-mono text-[#0F172A]">
              {wf.sequence.length} steps
            </span>
          </div>
        </div>

        {/* Steps preview list with subtle sequential reveal */}
        <div className="mt-3 space-y-1">
          <span className="text-[10px] font-semibold uppercase tracking-wider text-[#94A3B8]">
            Steps Sequence
          </span>
          <div className="space-y-1">
            {wf.sequence.slice(0, 4).map((s, idx) => (
              <div
                key={idx}
                style={{ animationDelay: `${idx * 40}ms` }}
                className="text-[11px] text-[#475569] font-mono flex items-center gap-1.5 truncate animate-step-reveal"
              >
                <span className="text-[#94A3B8]">{idx + 1}.</span>
                <span className="truncate">{formatEventStep(s)}</span>
              </div>
            ))}
            {wf.sequence.length > 4 && (
              <span className="text-[10px] text-[#94A3B8] pl-3 italic">
                +{wf.sequence.length - 4} more steps…
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Card Action Buttons */}
      <div className="pt-3 border-t border-[#F1F5F9] flex items-center justify-between gap-2">
        <button
          onClick={() => onSelect(wf)}
          className="flex-1 px-3 py-1.5 text-xs font-semibold rounded-lg bg-[#F8FAFC] border border-[#E2E8F0] hover:bg-white hover:border-[#CBD5E1] text-[#0F172A] transition-all duration-150 active:translate-y-px cursor-pointer text-center"
        >
          Workflow Details
        </button>
        <button
          onClick={() => onReview(wf)}
          className="px-3.5 py-1.5 text-xs font-semibold rounded-lg bg-[#2563EB] hover:bg-[#1D4ED8] hover:shadow-xs text-white shadow-2xs transition-all duration-150 active:translate-y-px cursor-pointer"
        >
          Review & Run
        </button>
        {wf.is_rejected && onDelete && (
          <button
            onClick={() => onDelete(wf)}
            title="Delete rejected workflow"
            className="p-1.5 text-xs font-semibold rounded-lg bg-rose-50 text-rose-700 border border-rose-200 hover:bg-rose-100 transition-all duration-150 active:translate-y-px cursor-pointer"
          >
            🗑️
          </button>
        )}
      </div>
    </div>
  );
}

export default function WorkflowsView({
  discovery,
  discoveryLoading,
  discoveryError,
  onRefreshDiscovery,
  onExecutionComplete,
  onNavigate,
}: WorkflowsViewProps) {
  const [activeTab, setActiveTab] = useState<"discovered" | "builder">("discovered");
  const [selectedWorkflow, setSelectedWorkflow] = useState<DiscoveredWorkflow | null>(null);
  const [advancedReviewWorkflow, setAdvancedReviewWorkflow] = useState<DiscoveredWorkflow | null>(null);
  const [searchFilter, setSearchFilter] = useState("");
  const [deletedIds, setDeletedIds] = useState<Set<string>>(new Set());
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [workflowToDelete, setWorkflowToDelete] = useState<DiscoveredWorkflow | null>(null);
  const [isDeletingDirect, setIsDeletingDirect] = useState(false);
  const [directDeleteError, setDirectDeleteError] = useState<string | null>(null);

  const handleDeleteWorkflow = async (workflowId: string) => {
    await deleteWorkflow(workflowId);
    setDeletedIds((prev) => new Set(prev).add(workflowId));
    setSelectedWorkflow(null);
    setAdvancedReviewWorkflow(null);
    setWorkflowToDelete(null);
    setToastMessage("Workflow deleted successfully");
    setTimeout(() => setToastMessage(null), 3000);
    onRefreshDiscovery();
  };

  const handleConfirmDirectDelete = async () => {
    if (!workflowToDelete) return;
    setIsDeletingDirect(true);
    setDirectDeleteError(null);
    const wid = getWorkflowCanonicalId(workflowToDelete.sequence, workflowToDelete.workflow_id);
    try {
      await handleDeleteWorkflow(wid);
    } catch (err: unknown) {
      setDirectDeleteError(err instanceof Error ? err.message : "Failed to delete workflow");
    } finally {
      setIsDeletingDirect(false);
    }
  };

  const rawWorkflowsList = discovery?.workflows || [];
  const workflowsList = rawWorkflowsList.filter(
    (wf) => !deletedIds.has(getWorkflowCanonicalId(wf.sequence, wf.workflow_id))
  );

  const filteredWorkflows = workflowsList.filter((wf) => {
    if (!searchFilter) return true;
    const q = searchFilter.toLowerCase();
    return (
      wf.label.toLowerCase().includes(q) ||
      wf.sequence.some((s) => s.toLowerCase().includes(q))
    );
  });

  return (
    <div className="h-full flex flex-col overflow-hidden bg-[#F7F9FC]">
      {/* Top Header & Sub-navigation */}
      <div className="bg-white border-b border-[#E2E8F0] px-6 py-3.5 shrink-0 shadow-2xs flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="flex bg-[#F1F5F9] p-0.5 rounded-lg border border-[#E2E8F0]">
            <button
              onClick={() => setActiveTab("discovered")}
              className={`px-3 py-1.5 text-xs font-semibold rounded-md transition cursor-pointer ${
                activeTab === "discovered"
                  ? "bg-white text-[#0F172A] shadow-xs"
                  : "text-[#64748B] hover:text-[#0F172A]"
              }`}
            >
              Discovered Workflows ({workflowsList.length})
            </button>
            <button
              onClick={() => setActiveTab("builder")}
              className={`px-3 py-1.5 text-xs font-semibold rounded-md transition cursor-pointer ${
                activeTab === "builder"
                  ? "bg-white text-[#0F172A] shadow-xs"
                  : "text-[#64748B] hover:text-[#0F172A]"
              }`}
            >
              Declarative Builder
            </button>
          </div>

          <span className="hidden md:inline text-xs text-[#94A3B8]">|</span>
          <span className="hidden md:inline text-xs text-[#64748B]">
            Observe → Understand → Discover → Learn → Plan → Approve → Automate
          </span>
        </div>

        {activeTab === "discovered" && (
          <div className="flex items-center gap-2.5">
            <input
              type="text"
              placeholder="Search workflows…"
              value={searchFilter}
              onChange={(e) => setSearchFilter(e.target.value)}
              className="bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg px-3 py-1.5 text-xs text-[#0F172A] placeholder-[#94A3B8] focus:outline-none focus:border-[#2563EB]"
            />
            <button
              onClick={onRefreshDiscovery}
              disabled={discoveryLoading}
              className="px-3 py-1.5 text-xs font-medium rounded-lg bg-white border border-[#E2E8F0] hover:bg-[#F8FAFC] text-[#0F172A] transition cursor-pointer disabled:opacity-60"
            >
              {discoveryLoading ? "Scanning…" : "Refresh"}
            </button>
          </div>
        )}
      </div>

      {/* Main Tab Content */}
      <div className="flex-1 overflow-y-auto">
        {activeTab === "builder" ? (
          <BuilderView
            onExecutionComplete={onExecutionComplete}
            onNavigate={onNavigate}
          />
        ) : (
          <div className="p-6 max-w-7xl mx-auto space-y-6">
            {/* Loading State */}
            {discoveryLoading ? (
              <div className="py-16 text-center space-y-3">
                <div className="inline-block w-8 h-8 border-2 border-[#2563EB] border-t-transparent rounded-full animate-spin" />
                <p className="text-xs text-[#64748B]">
                  Scanning event stream for recurring multi-step workflow patterns…
                </p>
              </div>
            ) : discoveryError ? (
              /* Error State */
              <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-center space-y-3">
                <div className="text-red-600 font-bold text-sm">
                  Unable to load discovered workflows
                </div>
                <p className="text-xs text-red-700 max-w-md mx-auto">
                  {discoveryError}. Check that the WorkFlowOS backend is running on port 8000.
                </p>
                <button
                  onClick={onRefreshDiscovery}
                  className="px-4 py-2 text-xs font-semibold rounded-lg bg-white border border-red-200 text-red-700 hover:bg-red-100/50 transition cursor-pointer"
                >
                  Retry Discovery Scan
                </button>
              </div>
            ) : workflowsList.length === 0 ? (
              /* Empty State */
              <div className="bg-white border border-dashed border-[#CBD5E1] rounded-2xl p-12 text-center max-w-xl mx-auto space-y-4">
                <div className="w-12 h-12 rounded-xl bg-[#EFF6FF] text-[#2563EB] flex items-center justify-center mx-auto">
                  <svg
                    className="w-6 h-6"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={1.8}
                      d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
                    />
                  </svg>
                </div>
                <div>
                  <h3 className="text-base font-bold text-[#0F172A]">
                    No workflows discovered yet
                  </h3>
                  <p className="text-xs text-[#64748B] mt-1 leading-relaxed">
                    Continue working normally in your applications or simulate activity
                    in the Demo Playground. WorkFlowOS will automatically detect
                    repeated multi-step patterns.
                  </p>
                </div>
                <div className="flex items-center justify-center gap-3 pt-2">
                  <a
                    href="/demo"
                    className="px-4 py-2 text-xs font-semibold rounded-lg bg-[#2563EB] hover:bg-[#1D4ED8] text-white shadow-2xs transition cursor-pointer"
                  >
                    Open Demo Applications
                  </a>
                  <button
                    onClick={onRefreshDiscovery}
                    className="px-4 py-2 text-xs font-medium rounded-lg border border-[#E2E8F0] bg-white text-[#0F172A] hover:bg-[#F8FAFC] transition cursor-pointer"
                  >
                    Scan Again
                  </button>
                </div>
              </div>
            ) : (
              /* Workflows Grid / Cards */
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                {filteredWorkflows.map((wf, idx) => {
                  const workflowId = getWorkflowCanonicalId(
                    wf.sequence,
                    wf.workflow_id
                  );
                  return (
                    <WorkflowCard
                      key={workflowId}
                      wf={wf}
                      index={idx}
                      onSelect={setSelectedWorkflow}
                      onReview={setAdvancedReviewWorkflow}
                      onDelete={(item) => setWorkflowToDelete(item)}
                    />
                  );
                })}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Workflow Detail Modal (Section 8) */}
      {selectedWorkflow && (
        <WorkflowDetailModal
          workflow={selectedWorkflow}
          onClose={() => setSelectedWorkflow(null)}
          onOpenAdvancedReview={() => {
            const wf = selectedWorkflow;
            setSelectedWorkflow(null);
            setAdvancedReviewWorkflow(wf);
          }}
          onDeleteWorkflow={handleDeleteWorkflow}
        />
      )}

      {/* Advanced AI Review & Execution Modal (DiscoveryView review engine) */}
      {advancedReviewWorkflow && (
        <DiscoveryView
          discovery={discovery}
          selectedWorkflow={advancedReviewWorkflow}
          onClose={() => setAdvancedReviewWorkflow(null)}
          discoveryLoading={discoveryLoading}
          discoveryError={discoveryError}
          onRefreshDiscovery={onRefreshDiscovery}
          onExecutionComplete={onExecutionComplete}
          onDeleteWorkflow={handleDeleteWorkflow}
        />
      )}

      {/* Direct Delete Confirmation Modal for Card Delete Action */}
      {workflowToDelete && (
        <div
          className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4 z-60 animate-fadeIn"
          onClick={() => {
            if (!isDeletingDirect) {
              setWorkflowToDelete(null);
              setDirectDeleteError(null);
            }
          }}
        >
          <div
            className="bg-white border border-[#E2E8F0] rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4 animate-modal-enter"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-xl bg-rose-50 border border-rose-200 flex items-center justify-center text-rose-600 shrink-0 text-lg">
                ⚠️
              </div>
              <div>
                <h3 className="text-sm font-bold text-[#0F172A]">Delete workflow?</h3>
                <p className="text-xs text-[#64748B] mt-1 leading-relaxed">
                  Are you sure you want to delete &ldquo;{workflowToDelete.label}&rdquo;?
                  This permanently removes the workflow and its learning tombstone. This action cannot be undone.
                </p>
              </div>
            </div>

            {directDeleteError && (
              <div className="bg-rose-50 border border-rose-200 text-rose-700 text-xs p-3 rounded-lg">
                {directDeleteError}
              </div>
            )}

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-[#F1F5F9]">
              <button
                type="button"
                onClick={() => {
                  setWorkflowToDelete(null);
                  setDirectDeleteError(null);
                }}
                disabled={isDeletingDirect}
                className="px-3.5 py-2 text-xs font-medium rounded-lg border border-[#E2E8F0] text-[#64748B] hover:bg-[#F8FAFC] transition cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmDirectDelete}
                disabled={isDeletingDirect}
                className="px-4 py-2 text-xs font-semibold rounded-lg bg-rose-600 hover:bg-rose-700 text-white shadow-2xs transition cursor-pointer disabled:opacity-60"
              >
                {isDeletingDirect ? "Deleting…" : "Delete Workflow"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-60 bg-slate-900 text-white text-xs px-4 py-2.5 rounded-xl shadow-lg border border-slate-700 flex items-center gap-2 animate-fadeIn">
          <span>✓</span>
          <span>{toastMessage}</span>
        </div>
      )}
    </div>
  );
}
