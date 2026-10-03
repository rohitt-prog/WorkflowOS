"use client";

import React, { useState } from "react";
import { WorkflowDefinition, WorkflowStep } from "@/lib/types";
import { API_BASE_URL, getApplicationDisplayName } from "@/lib/utils";

const DEFAULT_WORKFLOW: WorkflowDefinition = {
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

const STEP_TYPES = [
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
  "demo_email",
  "demo_crm",
  "demo_chat",
  "demo_messaging",
  "browser",
];

interface BuilderViewProps {
  onExecutionComplete: () => void;
}

export default function BuilderView({ onExecutionComplete }: BuilderViewProps) {
  const [workflow, setWorkflow] = useState<WorkflowDefinition>(DEFAULT_WORKFLOW);
  const [isRunning, setIsRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [runResult, setRunResult] = useState<Record<string, unknown> | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);
  const [testCustomer, setTestCustomer] = useState("Rahul");

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
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Save failed (${res.status})`);
      }
      const data = await res.json();
      setSaveMsg(`Saved successfully as ID: ${data.workflow_id || data.id || "registered"}`);
    } catch (e: unknown) {
      setSaveMsg(`Error: ${e instanceof Error ? e.message : "Save failed"}`);
    } finally {
      setIsSaving(false);
    }
  };

  const handleRun = async () => {
    setIsRunning(true);
    setRunError(null);
    setRunResult(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/automation/execute`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          workflow_definition: workflow,
          approved: true,
          inputs: { customer_name: testCustomer },
          parameters: { customer_name: testCustomer },
          executor_type: "playwright",
        }),
      });

      const data = await res.json();
      setRunResult(data);
      onExecutionComplete();
    } catch (e: unknown) {
      setRunError(e instanceof Error ? e.message : "Execution failed");
    } finally {
      setIsRunning(false);
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
              Phase 6 Engine
            </span>
          </div>
          <p className="text-xs text-[#64748B] mt-0.5">
            Configure multi-step workflows with variable extraction, retry policies, and conditional branching.
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
            onClick={handleRun}
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

        <div className="pt-3 border-t border-[#E2E8F0] flex items-center justify-between text-xs">
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

          <div className="flex items-center gap-2">
            <span className="text-[#64748B]">Test Input:</span>
            <input
              type="text"
              value={testCustomer}
              onChange={(e) => setTestCustomer(e.target.value)}
              className="w-32 bg-[#F8FAFC] border border-[#E2E8F0] rounded px-2 py-1 text-xs text-[#0F172A] font-mono focus:outline-none focus:border-[#2563EB]"
            />
          </div>
        </div>
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
                    onChange={(e) => updateStep(idx, { type: e.target.value })}
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
                    onChange={(e) => updateStep(idx, { application: e.target.value })}
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

      {/* Execution Result Box */}
      {runError && (
        <div className="bg-rose-50 border border-rose-200 rounded-xl p-4 text-xs text-rose-700">
          <span className="font-semibold">Execution Failed: </span>
          {runError}
        </div>
      )}

      {runResult && (
        <section className="bg-white border border-[#E2E8F0] rounded-xl p-5 space-y-3 shadow-2xs">
          <div className="flex items-center justify-between">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-[#0F172A]">
              Test Run Output
            </h4>
            <span
              className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${
                runResult.status === "completed"
                  ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                  : "bg-amber-50 text-amber-700 border-amber-200"
              }`}
            >
              {String(runResult.status || "completed")}
            </span>
          </div>
          <pre className="font-mono text-[11px] text-[#0F172A] bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg p-3 overflow-x-auto max-h-60">
            {JSON.stringify(runResult, null, 2)}
          </pre>
        </section>
      )}
    </div>
  );
}
