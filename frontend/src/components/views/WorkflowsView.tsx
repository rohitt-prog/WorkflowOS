"use client";

import React, { useState, useEffect } from "react";
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
}

function WorkflowDetailModal({
  workflow,
  onClose,
  onOpenAdvancedReview,
}: WorkflowDetailModalProps) {
  const [learning, setLearning] = useState<WorkflowLearningState | null>(null);
  const [plan, setPlan] = useState<AutomationPlan | null>(null);
  const [closedLoop, setClosedLoop] = useState<ClosedLoopSummary | null>(null);
  const [loadingDetails, setLoadingDetails] = useState(true);

  const wfId = getWorkflowCanonicalId(workflow.sequence, workflow.workflow_id);

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

  return (
    <div
      className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4 z-50 animate-fadeIn"
      onClick={onClose}
    >
      <div
        className="bg-white border border-[#E2E8F0] rounded-2xl max-w-2xl w-full shadow-2xl flex flex-col max-h-[90vh] overflow-hidden"
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
            className="text-[#94A3B8] hover:text-[#0F172A] p-1 rounded hover:bg-[#E2E8F0] transition cursor-pointer"
          >
            ✕
          </button>
        </div>

        {/* Scrollable Content Body */}
        <div className="p-6 overflow-y-auto space-y-5 text-xs flex-1">
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
          <button
            onClick={onClose}
            className="px-3.5 py-2 text-xs font-medium rounded-lg border border-[#E2E8F0] text-[#64748B] hover:bg-white hover:text-[#0F172A] transition cursor-pointer"
          >
            Close
          </button>
          <button
            onClick={() => {
              onClose();
              onOpenAdvancedReview();
            }}
            className="flex items-center gap-1.5 px-4 py-2 text-xs font-semibold rounded-lg bg-[#2563EB] hover:bg-[#1D4ED8] text-white shadow-2xs transition active:scale-97 cursor-pointer"
          >
            <span>Review & Automate</span>
            <span>→</span>
          </button>
        </div>
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

  const workflowsList = discovery?.workflows || [];

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
                {filteredWorkflows.map((wf) => {
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

                  return (
                    <div
                      key={wf.label}
                      className="bg-white border border-[#E2E8F0] rounded-xl p-5 shadow-2xs hover:shadow-xs hover:border-[#CBD5E1] transition flex flex-col justify-between space-y-4"
                    >
                      <div>
                        {/* Status & Confidence row */}
                        <div className="flex items-center justify-between gap-2 mb-2">
                          <span
                            className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase border ${
                              status === "RECOMMENDED"
                                ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                                : "bg-blue-50 text-blue-700 border-blue-200"
                            }`}
                          >
                            {status}
                          </span>
                          <span className="text-[11px] font-mono text-[#64748B]">
                            Confidence: <strong className="text-[#0F172A]">{conf}%</strong>
                          </span>
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
                              {wf.occurrences} observed sessions
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

                        {/* Steps preview list */}
                        <div className="mt-3 space-y-1">
                          <span className="text-[10px] font-semibold uppercase tracking-wider text-[#94A3B8]">
                            Steps Sequence
                          </span>
                          <div className="space-y-1">
                            {wf.sequence.slice(0, 4).map((s, idx) => (
                              <div
                                key={idx}
                                className="text-[11px] text-[#475569] font-mono flex items-center gap-1.5 truncate"
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
                          onClick={() => setSelectedWorkflow(wf)}
                          className="flex-1 px-3 py-1.5 text-xs font-semibold rounded-lg bg-[#F8FAFC] border border-[#E2E8F0] hover:bg-white text-[#0F172A] transition cursor-pointer text-center"
                        >
                          Workflow Details
                        </button>
                        <button
                          onClick={() => setAdvancedReviewWorkflow(wf)}
                          className="px-3.5 py-1.5 text-xs font-semibold rounded-lg bg-[#2563EB] hover:bg-[#1D4ED8] text-white shadow-2xs transition active:scale-97 cursor-pointer"
                        >
                          Review & Run
                        </button>
                      </div>
                    </div>
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
        />
      )}

      {/* Advanced AI Review & Execution Modal (DiscoveryView review engine) */}
      {advancedReviewWorkflow && (
        <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl w-full max-w-5xl max-h-[92vh] overflow-hidden flex flex-col shadow-2xl">
            <div className="p-4 border-b border-[#E2E8F0] flex items-center justify-between bg-[#F8FAFC]">
              <div>
                <span className="text-[10px] font-semibold uppercase tracking-wider text-[#64748B]">
                  Workflow Automation Studio
                </span>
                <h3 className="text-sm font-bold text-[#0F172A]">
                  Review & Execute: {advancedReviewWorkflow.label}
                </h3>
              </div>
              <button
                onClick={() => setAdvancedReviewWorkflow(null)}
                className="text-[#94A3B8] hover:text-[#0F172A] p-1.5 rounded hover:bg-[#E2E8F0] transition cursor-pointer"
              >
                ✕ Close
              </button>
            </div>
            <div className="flex-1 overflow-y-auto">
              <DiscoveryView
                discovery={discovery}
                discoveryLoading={discoveryLoading}
                discoveryError={discoveryError}
                onRefreshDiscovery={onRefreshDiscovery}
                onExecutionComplete={onExecutionComplete}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
