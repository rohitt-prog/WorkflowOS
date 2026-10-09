"use client";

import React, { useState } from "react";
import { WorkflowDefinition, WorkflowStep, ViewId, AutomationExecutionResponse } from "@/lib/types";
import { API_BASE_URL, getApplicationDisplayName, formatApiErrorMessage } from "@/lib/utils";
import WorkflowVisualizer, {
  GMAIL_TRIAGE_PIPELINE_DEF,
} from "@/components/WorkflowVisualizer";

const DEFAULT_WORKFLOW: WorkflowDefinition = {
  id: "wf_customer_verification",
  name: "Customer Verification & Update",
  description: "Automated customer inquiry handling across Email, CRM, and Chat.",
  trigger: { type: "manual", application: "", event: "" },
  inputs: [
    {
      name: "customer_name",
      type: "string",
      description: "Target customer name for CRM query",
      required: true,
      default: "Rahul",
    },
  ],
  steps: [
    {
      id: "step_1",
      name: "Open Customer Email",
      type: "open_email",
      application: "demo_email",
      parameters: {},
    },
    {
      id: "step_2",
      name: "Download PDF Attachment",
      type: "download_attachment",
      application: "demo_email",
      parameters: { filename: "customer_request.pdf" },
    },
    {
      id: "step_3",
      name: "Search Customer in CRM",
      type: "search_customer",
      application: "demo_crm",
      parameters: { customer_name: "{{inputs.customer_name}}" },
      condition: {
        field: "{{inputs.customer_name}}",
        operator: "not_empty",
      },
      retry_policy: {
        max_attempts: 2,
        delay_seconds: 1,
      },
    },
    {
      id: "step_4",
      name: "Update CRM Notes",
      type: "update_customer",
      application: "demo_crm",
      parameters: {
        notes: "Account verified from email attachment. High-priority enterprise support status activated.",
      },
    },
    {
      id: "step_5",
      name: "Send Confirmation via Chat",
      type: "send_message",
      application: "demo_chat",
      parameters: {
        message: "Customer record updated in CRM with VIP tier. Request document verified.",
      },
    },
  ],
  requires_approval: true,
  tags: ["enterprise", "crm", "email"],
};

const GMAIL_TRIAGE_WORKFLOW: WorkflowDefinition = GMAIL_TRIAGE_PIPELINE_DEF;

const STEP_TYPES = [
  "list_recent_messages",
  "open_email",
  "download_attachment",
  "search_customer",
  "update_customer",
  "send_message",
  "navigate",
  "click",
  "type",
  "extract",
  "condition",
];

const APPLICATIONS = [
  "gmail",
  "demo_email",
  "demo_crm",
  "demo_chat",
  "demo_messaging",
  "browser",
];

interface BuilderViewProps {
  onExecutionComplete: () => void;
  onNavigate?: (view: ViewId) => void;
}

export default function BuilderView({ onExecutionComplete, onNavigate }: BuilderViewProps) {
  const [workflow, setWorkflow] = useState<WorkflowDefinition>(DEFAULT_WORKFLOW);
  const [activePreset, setActivePreset] = useState<"default" | "gmail">("default");
  const [gmailStatus, setGmailStatus] = useState<{ is_connected: boolean; email_address?: string } | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [runResult, setRunResult] = useState<AutomationExecutionResponse | null>(null);
  const [showApprovalModal, setShowApprovalModal] = useState(false);
  const [dismissBanner, setDismissBanner] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);
  const [testCustomer, setTestCustomer] = useState("Rahul");
  const [testQuery, setTestQuery] = useState("label:INBOX");

  React.useEffect(() => {
    let isMounted = true;
    fetch(`${API_BASE_URL}/api/integrations/gmail/status`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (isMounted && data) {
          setGmailStatus(data);
        }
      })
      .catch(() => {});
    return () => {
      isMounted = false;
    };
  }, []);

  const updateStep = (idx: number, updates: Partial<WorkflowStep>) => {
    setWorkflow((prev) => {
      const steps = [...prev.steps];
      steps[idx] = { ...steps[idx], ...updates };
      return { ...prev, steps };
    });
  };

  const addStep = () => {
    const newStep: WorkflowStep = {
      id: `step_${workflow.steps.length + 1}`,
      name: "New Action Step",
      type: "open_email",
      application: "demo_email",
      parameters: {},
    };
    setWorkflow((prev) => ({ ...prev, steps: [...prev.steps, newStep] }));
  };

  const removeStep = (idx: number) => {
    setWorkflow((prev) => ({
      ...prev,
      steps: prev.steps.filter((_, i) => i !== idx),
    }));
  };

  const moveStep = (idx: number, dir: -1 | 1) => {
    const newIdx = idx + dir;
    if (newIdx < 0 || newIdx >= workflow.steps.length) return;
    setWorkflow((prev) => {
      const steps = [...prev.steps];
      [steps[idx], steps[newIdx]] = [steps[newIdx], steps[idx]];
      return { ...prev, steps };
    });
  };

  const handleSave = async () => {
    setIsSaving(true);
    setSaveMsg(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/automation/workflows`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(workflow),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => null);
        throw new Error(formatApiErrorMessage(err, `Save failed (${res.status})`));
      }
      const data = await res.json();
      const assignedId = data.id || data.workflow_id || "registered";
      setWorkflow((prev) => ({ ...prev, id: assignedId }));
      setSaveMsg(`Saved successfully as ID: ${assignedId}`);
    } catch (e: unknown) {
      setSaveMsg(`Error: ${e instanceof Error ? e.message : "Save failed"}`);
    } finally {
      setIsSaving(false);
    }
  };

  const executeWorkflow = async (approved: boolean) => {
    setIsRunning(true);
    setRunError(null);
    setRunResult(null);
    setDismissBanner(false);
    try {
      const inputsPayload: Record<string, unknown> = {
        customer_name: testCustomer,
        query: testQuery,
        max_results: 5,
      };
      const res = await fetch(`${API_BASE_URL}/api/automation/execute`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          workflow_definition: workflow,
          approved: approved,
          inputs: inputsPayload,
          parameters: inputsPayload,
          executor_type: "playwright",
        }),
      });

      const data = await res.json().catch(() => null);

      if (!res.ok) {
        throw new Error(formatApiErrorMessage(data, `Execution failed (${res.status})`));
      }

      setRunResult(data);
      onExecutionComplete();
    } catch (e: unknown) {
      setRunError(e instanceof Error ? e.message : "Execution failed");
    } finally {
      setIsRunning(false);
    }
  };

  const handleTestRunClick = () => {
    if (workflow.requires_approval) {
      setShowApprovalModal(true);
    } else {
      executeWorkflow(true);
    }
  };

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6 bg-[#F7F9FC]">
      {/* Top Banner & Action Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white border border-[#E2E8F0] rounded-xl p-5 shadow-2xs">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-bold text-[#0F172A] tracking-tight">
              Declarative Workflow Builder
            </h2>
            <span className="text-[10px] font-semibold uppercase px-2 py-0.5 rounded-full bg-blue-50 text-[#2563EB] border border-blue-200">
              Phase 7.3 Integration Engine
            </span>
          </div>
          <p className="text-xs text-[#64748B] mt-0.5">
            Configure multi-step workflows across native apps, mock adapters, and Gmail OAuth.
          </p>
        </div>
        <div className="flex items-center gap-2.5 shrink-0">
          <button
            onClick={handleSave}
            disabled={isSaving}
            className="px-4 py-2 text-xs font-semibold rounded-lg bg-white hover:bg-[#F8FAFC] border border-[#E2E8F0] text-[#0F172A] shadow-2xs transition active:scale-97 disabled:opacity-60 cursor-pointer"
          >
            {isSaving ? "Saving…" : "Save Definition"}
          </button>
          <button
            onClick={handleTestRunClick}
            disabled={isRunning}
            className="flex items-center gap-1.5 px-4 py-2 text-xs font-semibold rounded-lg bg-[#2563EB] hover:bg-[#1D4ED8] text-white shadow-2xs transition active:scale-97 disabled:opacity-60 cursor-pointer"
          >
            {isRunning ? (
              <>
                <span className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
                <span>Running…</span>
              </>
            ) : (
              <>
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                  <path strokeLinecap="round" strokeLinejoin="round" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span>Test Run Workflow</span>
              </>
            )}
          </button>
        </div>
      </div>

      {saveMsg && (
        <div
          className={`p-3.5 rounded-xl border text-xs ${
            saveMsg.startsWith("Error")
              ? "bg-rose-50 border-rose-200 text-rose-700"
              : "bg-emerald-50 border-emerald-200 text-emerald-700"
          }`}
        >
          {saveMsg}
        </div>
      )}

      {/* Top Prominent Execution Status Banner */}
      {isRunning && (
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 flex items-center justify-between gap-3 shadow-2xs animate-pulse">
          <div className="flex items-center gap-3">
            <span className="w-4 h-4 border-2 border-[#2563EB] border-t-transparent rounded-full animate-spin shrink-0" />
            <div>
              <p className="text-xs font-semibold text-[#0F172A]">
                Executing Workflow: {workflow.name}...
              </p>
              <p className="text-[11px] text-[#64748B] mt-0.5">
                Executing {workflow.steps.length} actions across {Array.from(new Set(workflow.steps.map((s) => getApplicationDisplayName(s.application)))).join(", ")}
              </p>
            </div>
          </div>
          <span className="text-[10px] font-mono font-medium px-2 py-0.5 rounded bg-blue-100 text-[#2563EB] border border-blue-300">
            IN PROGRESS
          </span>
        </div>
      )}

      {runError && !dismissBanner && (
        <div className="bg-rose-50 border border-rose-200 rounded-xl p-4 shadow-2xs">
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-start gap-3">
              <span className="text-rose-500 font-bold text-sm leading-none mt-0.5">✕</span>
              <div>
                <p className="text-xs font-semibold text-rose-900">
                  Execution Failed
                </p>
                <p className="text-xs text-rose-700 mt-1 font-mono whitespace-pre-wrap">
                  {runError}
                </p>
              </div>
            </div>
            <button
              onClick={() => setDismissBanner(true)}
              className="text-xs text-rose-500 hover:text-rose-700 cursor-pointer font-medium"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      {runResult && !dismissBanner && runResult.status === "completed" && (
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 shadow-2xs">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-start gap-3">
              <span className="w-5 h-5 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center font-bold text-xs shrink-0 mt-0.5">
                ✓
              </span>
              <div>
                <div className="flex items-center gap-2">
                  <p className="text-xs font-semibold text-emerald-950">
                    Workflow Completed Successfully
                  </p>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-300">
                    {runResult.completed_actions?.length ?? workflow.steps.length}/{workflow.steps.length} actions
                  </span>
                </div>
                <p className="text-xs text-emerald-700 mt-0.5">
                  Execution ID: <span className="font-mono font-semibold">{runResult.workflow_id}</span>
                  {typeof runResult.execution_time_seconds === "number" && (
                    <span className="ml-2 font-mono text-[11px] text-emerald-600">
                      ({runResult.execution_time_seconds.toFixed(2)}s)
                    </span>
                  )}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2 self-end sm:self-center">
              {onNavigate && (
                <button
                  onClick={() => onNavigate("executions")}
                  className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white shadow-2xs transition active:scale-97 cursor-pointer"
                >
                  View in Executions →
                </button>
              )}
              <button
                onClick={() => setDismissBanner(true)}
                className="text-xs text-emerald-600 hover:text-emerald-800 px-2 py-1 cursor-pointer font-medium"
              >
                Dismiss
              </button>
            </div>
          </div>
        </div>
      )}

      {runResult && !dismissBanner && runResult.status === "paused" && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 shadow-2xs">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-start gap-3">
              <span className="w-5 h-5 rounded-full bg-amber-100 text-amber-700 flex items-center justify-center font-bold text-xs shrink-0 mt-0.5">
                ⏸
              </span>
              <div>
                <div className="flex items-center gap-2">
                  <p className="text-xs font-semibold text-amber-950">
                    Workflow Paused — Human Intervention Required
                  </p>
                  {runResult.failed_action && (
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 border border-amber-300">
                      Step: {runResult.failed_action}
                    </span>
                  )}
                </div>
                <p className="text-xs text-amber-800 mt-0.5">
                  Execution ID: <span className="font-mono font-semibold">{runResult.workflow_id}</span>
                </p>
                <p className="text-xs text-amber-700 mt-1">
                  Reason: {runResult.failure_reason || runResult.message || "Action execution failed."}
                </p>
                {runResult.human_intervention?.action_required && (
                  <p className="text-xs text-amber-800 font-medium mt-1">
                    Required Action: {runResult.human_intervention.action_required}
                  </p>
                )}
              </div>
            </div>
            <div className="flex items-center gap-2 self-end sm:self-center">
              {onNavigate && (
                <button
                  onClick={() => onNavigate("executions")}
                  className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-amber-600 hover:bg-amber-700 text-white shadow-2xs transition active:scale-97 cursor-pointer"
                >
                  View in Executions →
                </button>
              )}
              <button
                onClick={() => setDismissBanner(true)}
                className="text-xs text-amber-700 hover:text-amber-900 px-2 py-1 cursor-pointer font-medium"
              >
                Dismiss
              </button>
            </div>
          </div>
        </div>
      )}

      {runResult && !dismissBanner && runResult.status === "pending" && (
        <div className="bg-sky-50 border border-sky-200 rounded-xl p-4 shadow-2xs">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-start gap-3">
              <span className="w-5 h-5 rounded-full bg-sky-100 text-sky-700 flex items-center justify-center font-bold text-xs shrink-0 mt-0.5">
                ⏱
              </span>
              <div>
                <p className="text-xs font-semibold text-sky-950">
                  Execution Queued (Pending Operator Approval)
                </p>
                <p className="text-xs text-sky-800 mt-0.5">
                  Execution ID: <span className="font-mono font-semibold">{runResult.workflow_id}</span>
                </p>
                <p className="text-xs text-sky-700 mt-1">
                  {runResult.message || "Human approval required before execution can proceed."}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2 self-end sm:self-center">
              {onNavigate && (
                <button
                  onClick={() => onNavigate("executions")}
                  className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-sky-600 hover:bg-sky-700 text-white shadow-2xs transition active:scale-97 cursor-pointer"
                >
                  Review in Executions →
                </button>
              )}
              <button
                onClick={() => setDismissBanner(true)}
                className="text-xs text-sky-600 hover:text-sky-800 px-2 py-1 cursor-pointer font-medium"
              >
                Dismiss
              </button>
            </div>
          </div>
        </div>
      )}

      {runResult && !dismissBanner && runResult.status === "failed" && (
        <div className="bg-rose-50 border border-rose-200 rounded-xl p-4 shadow-2xs">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-start gap-3">
              <span className="w-5 h-5 rounded-full bg-rose-100 text-rose-700 flex items-center justify-center font-bold text-xs shrink-0 mt-0.5">
                ✕
              </span>
              <div>
                <p className="text-xs font-semibold text-rose-950">
                  Workflow Execution Failed
                </p>
                <p className="text-xs text-rose-800 mt-0.5">
                  Execution ID: <span className="font-mono font-semibold">{runResult.workflow_id}</span>
                </p>
                <p className="text-xs text-rose-700 mt-1">
                  Reason: {runResult.failure_reason || runResult.message || "Workflow execution failed."}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2 self-end sm:self-center">
              {onNavigate && (
                <button
                  onClick={() => onNavigate("executions")}
                  className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-rose-600 hover:bg-rose-700 text-white shadow-2xs transition active:scale-97 cursor-pointer"
                >
                  View in Executions →
                </button>
              )}
              <button
                onClick={() => setDismissBanner(true)}
                className="text-xs text-rose-600 hover:text-rose-800 px-2 py-1 cursor-pointer font-medium"
              >
                Dismiss
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Preset Selector Banner */}
      <div className="flex items-center gap-2 bg-white border border-[#E2E8F0] rounded-xl p-3 shadow-2xs">
        <span className="text-xs font-semibold text-[#64748B] pl-2">Workflow Presets:</span>
        <button
          type="button"
          onClick={() => {
            setWorkflow(DEFAULT_WORKFLOW);
            setActivePreset("default");
          }}
          className={`px-3 py-1.5 text-xs rounded-lg font-medium transition cursor-pointer ${
            activePreset === "default"
              ? "bg-[#2563EB] text-white shadow-2xs"
              : "bg-[#F8FAFC] border border-[#E2E8F0] text-[#0F172A] hover:bg-[#F1F5F9]"
          }`}
        >
          Customer Verification (Demo)
        </button>
        <button
          type="button"
          onClick={() => {
            setWorkflow(GMAIL_TRIAGE_WORKFLOW);
            setActivePreset("gmail");
          }}
          className={`px-3 py-1.5 text-xs rounded-lg font-medium transition cursor-pointer flex items-center gap-1.5 ${
            activePreset === "gmail"
              ? "bg-rose-600 text-white shadow-2xs"
              : "bg-[#F8FAFC] border border-[#E2E8F0] text-[#0F172A] hover:bg-[#F1F5F9]"
          }`}
        >
          <span className="w-1.5 h-1.5 rounded-full bg-rose-400"></span>
          Gmail Inbox Triage & CRM (Phase 7.3)
        </button>
      </div>

      {/* Workflow Metadata Card */}
      <section className="bg-white border border-[#E2E8F0] rounded-xl p-5 space-y-4 shadow-2xs">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-[#64748B]">
          Workflow Metadata
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="text-xs font-semibold text-[#0F172A] block mb-1">
              Workflow Name
            </label>
            <input
              type="text"
              value={workflow.name}
              onChange={(e) => setWorkflow((prev) => ({ ...prev, name: e.target.value }))}
              className="w-full bg-white border border-[#E2E8F0] rounded-lg px-3 py-2 text-xs text-[#0F172A] focus:outline-none focus:border-[#2563EB]"
            />
          </div>
          <div>
            <label className="text-xs font-semibold text-[#0F172A] block mb-1">
              Description
            </label>
            <input
              type="text"
              value={workflow.description || ""}
              onChange={(e) => setWorkflow((prev) => ({ ...prev, description: e.target.value }))}
              placeholder="Workflow purpose and expected outcome…"
              className="w-full bg-white border border-[#E2E8F0] rounded-lg px-3 py-2 text-xs text-[#0F172A] focus:outline-none focus:border-[#2563EB]"
            />
          </div>
        </div>

        <div className="pt-3 border-t border-[#E2E8F0] flex flex-wrap items-center justify-between gap-3 text-xs">
          <label className="flex items-center gap-2 cursor-pointer text-[#0F172A]">
            <input
              type="checkbox"
              checked={workflow.requires_approval}
              onChange={(e) =>
                setWorkflow((prev) => ({ ...prev, requires_approval: e.target.checked }))
              }
              className="rounded border-[#E2E8F0] text-[#2563EB] focus:ring-0"
            />
            <span className="font-medium">Require operator approval before execution</span>
          </label>

          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5">
              <span className="text-[#64748B]">Customer:</span>
              <input
                type="text"
                value={testCustomer}
                onChange={(e) => setTestCustomer(e.target.value)}
                className="w-24 bg-[#F8FAFC] border border-[#E2E8F0] rounded px-2 py-1 text-xs text-[#0F172A] font-mono focus:outline-none focus:border-[#2563EB]"
              />
            </div>
            <div className="flex items-center gap-1.5">
              <span className="text-[#64748B]">Query:</span>
              <input
                type="text"
                value={testQuery}
                onChange={(e) => setTestQuery(e.target.value)}
                className="w-28 bg-[#F8FAFC] border border-[#E2E8F0] rounded px-2 py-1 text-xs text-[#0F172A] font-mono focus:outline-none focus:border-[#2563EB]"
              />
            </div>
          </div>
        </div>
      </section>

      {/* Visual Execution Pipeline Graph */}
      <section>
        <WorkflowVisualizer
          definition={workflow}
          execution={runResult}
          isExecuting={isRunning}
        />
      </section>

      {/* Step Sequence Builder */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-[#64748B]">
            Execution Steps ({workflow.steps.length})
          </h3>
          <button
            onClick={addStep}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-white hover:bg-[#F8FAFC] border border-[#E2E8F0] text-[#2563EB] shadow-2xs transition active:scale-97 cursor-pointer"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
            </svg>
            <span>Add Step</span>
          </button>
        </div>

        <div className="space-y-3">
          {workflow.steps.map((step, idx) => (
            <div
              key={step.id || idx}
              className="bg-white border border-[#E2E8F0] rounded-xl p-5 shadow-2xs space-y-4 hover:shadow-xs transition"
            >
              {/* Step Header */}
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <span className="w-6 h-6 rounded-full bg-[#EFF6FF] text-[#2563EB] font-bold text-xs flex items-center justify-center font-mono shrink-0">
                    {idx + 1}
                  </span>
                  <input
                    type="text"
                    value={step.name}
                    onChange={(e) => updateStep(idx, { name: e.target.value })}
                    className="font-bold text-xs text-[#0F172A] bg-transparent border-b border-transparent hover:border-[#E2E8F0] focus:border-[#2563EB] focus:outline-none px-1 py-0.5"
                  />
                  <span className="text-[10px] font-mono text-[#94A3B8]">
                    ({step.id})
                  </span>
                </div>

                <div className="flex items-center gap-1">
                  <button
                    onClick={() => moveStep(idx, -1)}
                    disabled={idx === 0}
                    className="p-1 rounded text-[#64748B] hover:text-[#0F172A] hover:bg-[#F1F5F9] disabled:opacity-30 cursor-pointer"
                    title="Move up"
                  >
                    ↑
                  </button>
                  <button
                    onClick={() => moveStep(idx, 1)}
                    disabled={idx === workflow.steps.length - 1}
                    className="p-1 rounded text-[#64748B] hover:text-[#0F172A] hover:bg-[#F1F5F9] disabled:opacity-30 cursor-pointer"
                    title="Move down"
                  >
                    ↓
                  </button>
                  <button
                    onClick={() => removeStep(idx)}
                    disabled={workflow.steps.length <= 1}
                    className="p-1 rounded text-rose-500 hover:text-rose-700 hover:bg-rose-50 disabled:opacity-30 cursor-pointer ml-1"
                    title="Delete step"
                  >
                    ✕
                  </button>
                </div>
              </div>

              {/* Step Action Config Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                <div>
                  <label className="text-[#64748B] font-medium block mb-1">
                    Action Type
                  </label>
                  <select
                    value={step.type}
                    onChange={(e) => {
                      const newType = e.target.value;
                      const updates: Partial<WorkflowStep> = { type: newType };
                      if (newType === "list_recent_messages") {
                        updates.application = "gmail";
                        updates.parameters = { max_results: 5, query: "label:INBOX" };
                      }
                      updateStep(idx, updates);
                    }}
                    className="w-full bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg px-3 py-2 text-xs text-[#0F172A] focus:outline-none focus:border-[#2563EB] cursor-pointer"
                  >
                    {STEP_TYPES.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="text-[#64748B] font-medium block mb-1">
                    Target Application
                  </label>
                  <select
                    value={step.application}
                    onChange={(e) => {
                      const newApp = e.target.value;
                      const updates: Partial<WorkflowStep> = { application: newApp };
                      if (newApp === "gmail") {
                        updates.type = "list_recent_messages";
                        updates.parameters = { max_results: 5, query: "label:INBOX" };
                      }
                      updateStep(idx, updates);
                    }}
                    className="w-full bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg px-3 py-2 text-xs text-[#0F172A] focus:outline-none focus:border-[#2563EB] cursor-pointer"
                  >
                    {APPLICATIONS.map((app) => (
                      <option key={app} value={app}>
                        {getApplicationDisplayName(app)} ({app})
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Step Parameters Configuration */}
              {(step.application === "gmail" || step.type === "list_recent_messages") && (
                <div className="space-y-3 pt-3 border-t border-[#E2E8F0]">
                  {gmailStatus && !gmailStatus.is_connected && (
                    <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 flex items-start gap-2 text-xs text-amber-800">
                      <span className="text-amber-600 font-bold shrink-0">⚠️</span>
                      <div className="space-y-0.5">
                        <span className="font-semibold block">Gmail Account Disconnected</span>
                        <span className="text-[11px] text-amber-700">
                          This step will fail or pause during execution. Please connect your Google account in Settings.
                        </span>
                      </div>
                    </div>
                  )}

                  {gmailStatus?.is_connected && (
                    <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-2.5 flex items-center justify-between text-xs text-emerald-800">
                      <div className="flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-emerald-600"></span>
                        <span className="font-medium">
                          Connected: {gmailStatus.email_address || "Google Account"}
                        </span>
                      </div>
                      <span className="text-[10px] font-semibold uppercase px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 border border-emerald-300">
                        Read-Only Scope
                      </span>
                    </div>
                  )}

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg p-3">
                    <div>
                      <label className="text-[11px] font-semibold text-[#64748B] block mb-1">
                        Max Results (1 – 20)
                      </label>
                      <input
                        type="number"
                        min={1}
                        max={20}
                        value={(step.parameters?.max_results as number) ?? 5}
                        onChange={(e) =>
                          updateStep(idx, {
                            parameters: {
                              ...step.parameters,
                              max_results: parseInt(e.target.value) || 5,
                            },
                          })
                        }
                        className="w-full bg-white border border-[#E2E8F0] rounded-lg px-2.5 py-1.5 text-xs text-[#0F172A] font-mono focus:outline-none focus:border-[#2563EB]"
                      />
                    </div>
                    <div>
                      <label className="text-[11px] font-semibold text-[#64748B] block mb-1">
                        Search Query Filter
                      </label>
                      <input
                        type="text"
                        placeholder="label:INBOX, is:unread, or {{inputs.query}}"
                        value={(step.parameters?.query as string) ?? ""}
                        onChange={(e) =>
                          updateStep(idx, {
                            parameters: {
                              ...step.parameters,
                              query: e.target.value,
                            },
                          })
                        }
                        className="w-full bg-white border border-[#E2E8F0] rounded-lg px-2.5 py-1.5 text-xs text-[#0F172A] font-mono focus:outline-none focus:border-[#2563EB]"
                      />
                    </div>
                  </div>
                </div>
              )}

              {/* Optional Advanced Config Accordion */}
              <div className="pt-3 border-t border-[#E2E8F0] grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                {/* Condition */}
                <div className="bg-[#F8FAFC] rounded-lg p-3 border border-[#E2E8F0] space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-[#0F172A] text-[11px]">
                      Conditional Branching
                    </span>
                    <button
                      onClick={() =>
                        updateStep(idx, {
                          condition: step.condition
                            ? undefined
                            : { field: "{{inputs.customer_name}}", operator: "not_empty" },
                        })
                      }
                      className="text-[10px] text-[#2563EB] hover:underline cursor-pointer"
                    >
                      {step.condition ? "Disable" : "+ Enable"}
                    </button>
                  </div>
                  {step.condition && (
                    <div className="space-y-1.5">
                      <input
                        type="text"
                        value={step.condition.field || ""}
                        onChange={(e) =>
                          updateStep(idx, {
                            condition: { ...step.condition!, field: e.target.value },
                          })
                        }
                        placeholder="Field / Variable expression…"
                        className="w-full bg-white border border-[#E2E8F0] rounded px-2 py-1 text-xs text-[#0F172A] font-mono"
                      />
                      <select
                        value={step.condition.operator}
                        onChange={(e) =>
                          updateStep(idx, {
                            condition: { ...step.condition!, operator: e.target.value },
                          })
                        }
                        className="w-full bg-white border border-[#E2E8F0] rounded px-2 py-1 text-xs text-[#0F172A]"
                      >
                        <option value="equals">equals</option>
                        <option value="not_equals">not_equals</option>
                        <option value="contains">contains</option>
                        <option value="not_empty">not_empty</option>
                      </select>
                    </div>
                  )}
                </div>

                {/* Retry Policy */}
                <div className="bg-[#F8FAFC] rounded-lg p-3 border border-[#E2E8F0] space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-[#0F172A] text-[11px]">
                      Retry Policy
                    </span>
                    <button
                      onClick={() =>
                        updateStep(idx, {
                          retry_policy: step.retry_policy
                            ? undefined
                            : { max_attempts: 3, delay_seconds: 1, backoff: "exponential" },
                        })
                      }
                      className="text-[10px] text-[#2563EB] hover:underline cursor-pointer"
                    >
                      {step.retry_policy ? "Disable" : "+ Enable"}
                    </button>
                  </div>
                  {step.retry_policy && (
                    <div className="grid grid-cols-2 gap-2 text-xs">
                      <div>
                        <label className="text-[10px] text-[#64748B] block">Max Retries</label>
                        <input
                          type="number"
                          value={step.retry_policy.max_attempts}
                          onChange={(e) =>
                            updateStep(idx, {
                              retry_policy: {
                                ...step.retry_policy!,
                                max_attempts: parseInt(e.target.value) || 1,
                              },
                            })
                          }
                          className="w-full bg-white border border-[#E2E8F0] rounded px-2 py-1 text-xs text-[#0F172A] font-mono"
                        />
                      </div>
                      <div>
                        <label className="text-[10px] text-[#64748B] block">Delay (sec)</label>
                        <input
                          type="number"
                          value={step.retry_policy.delay_seconds}
                          onChange={(e) =>
                            updateStep(idx, {
                              retry_policy: {
                                ...step.retry_policy!,
                                delay_seconds: parseInt(e.target.value) || 1,
                              },
                            })
                          }
                          className="w-full bg-white border border-[#E2E8F0] rounded px-2 py-1 text-xs text-[#0F172A] font-mono"
                        />
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Detailed Execution Output Box */}
      {runResult && (
        <section className="bg-white border border-[#E2E8F0] rounded-xl p-5 space-y-3 shadow-2xs">
          <div className="flex items-center justify-between">
            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wider text-[#0F172A]">
                Detailed Execution Output & Telemetry
              </h4>
              <p className="text-[11px] text-[#64748B] mt-0.5">
                Execution ID: <span className="font-mono font-medium text-[#0F172A]">{runResult.workflow_id}</span>
              </p>
            </div>
            <div className="flex items-center gap-2">
              <span
                className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${
                  runResult.status === "completed"
                    ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                    : runResult.status === "paused"
                    ? "bg-amber-50 text-amber-700 border-amber-200"
                    : runResult.status === "pending"
                    ? "bg-sky-50 text-sky-700 border-sky-200"
                    : "bg-rose-50 text-rose-700 border-rose-200"
                }`}
              >
                {String(runResult.status || "completed")}
              </span>
              {onNavigate && (
                <button
                  type="button"
                  onClick={() => onNavigate("executions")}
                  className="text-xs text-[#2563EB] hover:underline font-medium cursor-pointer"
                >
                  View in Executions →
                </button>
              )}
            </div>
          </div>
          <pre className="font-mono text-[11px] text-[#0F172A] bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg p-3 overflow-x-auto max-h-60">
            {JSON.stringify(runResult, null, 2)}
          </pre>
        </section>
      )}

      {/* Operator Approval Modal */}
      {showApprovalModal && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white border border-[#E2E8F0] rounded-2xl max-w-lg w-full p-6 shadow-xl space-y-4 animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-3">
              <div className="flex items-center gap-2.5">
                <span className="w-8 h-8 rounded-lg bg-amber-50 text-amber-600 border border-amber-200 flex items-center justify-center text-base font-bold shrink-0">
                  🛡
                </span>
                <div>
                  <h3 className="text-sm font-bold text-[#0F172A]">
                    Operator Approval Required
                  </h3>
                  <p className="text-[11px] text-[#64748B]">
                    Phase 7.3 Human-in-the-Loop Verification Gate
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setShowApprovalModal(false)}
                className="text-slate-400 hover:text-slate-600 p-1 rounded-md text-xs cursor-pointer"
              >
                ✕
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div className="bg-amber-50/70 border border-amber-200/80 rounded-lg p-3 text-amber-800 space-y-1">
                <p className="font-semibold">Review Automation Scope:</p>
                <p className="text-[11px] leading-relaxed">
                  This workflow is configured with <span className="font-semibold">operator approval required</span>. Confirm the actions below before dispatching execution to connected integrations and automation runners.
                </p>
              </div>

              <div className="border border-[#E2E8F0] rounded-lg p-3 space-y-2 bg-[#F8FAFC]">
                <div className="flex justify-between items-center text-[11px] text-[#64748B] border-b border-[#E2E8F0] pb-1.5">
                  <span className="font-semibold text-[#0F172A]">{workflow.name}</span>
                  <span className="font-mono text-[10px]">{workflow.steps.length} steps</span>
                </div>
                <div className="space-y-1.5">
                  {workflow.steps.map((step, idx) => (
                    <div key={step.id || idx} className="flex items-center justify-between text-[11px]">
                      <div className="flex items-center gap-1.5">
                        <span className="w-4 h-4 rounded-full bg-slate-200 text-slate-700 flex items-center justify-center text-[9px] font-bold">
                          {idx + 1}
                        </span>
                        <span className="font-medium text-[#0F172A]">{step.name || step.type}</span>
                        <span className="text-[#64748B]">({getApplicationDisplayName(step.application)})</span>
                      </div>
                      {step.application === "gmail" && (
                        <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200">
                          gmail.readonly
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2 text-[11px] bg-slate-50 border border-slate-200 rounded-lg p-2.5">
                <div>
                  <span className="text-slate-500 block">Customer Target:</span>
                  <span className="font-mono font-medium text-slate-800">{testCustomer || "None"}</span>
                </div>
                <div>
                  <span className="text-slate-500 block">Query / Filter:</span>
                  <span className="font-mono font-medium text-slate-800">{testQuery || "None"}</span>
                </div>
              </div>
            </div>

            <div className="flex items-center justify-between gap-2 pt-2 border-t border-[#E2E8F0]">
              <button
                type="button"
                onClick={() => {
                  setShowApprovalModal(false);
                  executeWorkflow(false);
                }}
                className="px-3 py-2 text-xs font-medium rounded-lg text-slate-600 hover:bg-slate-100 border border-slate-200 cursor-pointer transition"
                title="Submit without operator approval to verify backend approval gate"
              >
                Run Unapproved (Test Gate)
              </button>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setShowApprovalModal(false)}
                  className="px-3 py-2 text-xs font-medium rounded-lg text-[#0F172A] hover:bg-[#F1F5F9] border border-[#E2E8F0] cursor-pointer transition"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setShowApprovalModal(false);
                    executeWorkflow(true);
                  }}
                  className="px-4 py-2 text-xs font-semibold rounded-lg bg-[#2563EB] hover:bg-[#1D4ED8] text-white shadow-2xs cursor-pointer transition active:scale-97"
                >
                  Approve & Execute
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
