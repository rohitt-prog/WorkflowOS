"use client";

import React, { useState } from "react";
import { WorkflowDefinition, WorkflowStep } from "@/lib/types";
import { API_BASE_URL } from "@/lib/utils";

const DEFAULT_WORKFLOW: WorkflowDefinition = {
  name: "New Workflow",
  description: "",
  trigger: { type: "manual", application: "", event: "" },
  inputs: [],
  steps: [
    {
      id: "step_1",
      name: "First Step",
      type: "open_email",
      application: "demo_email",
      parameters: {},
    },
  ],
  requires_approval: true,
  tags: [],
};

const STEP_TYPES = [
  "open_email", "download_attachment", "search_customer", "update_customer",
  "send_message", "navigate", "click", "type", "extract", "condition",
];

const APPLICATIONS = [
  "demo_email", "demo_crm", "demo_chat", "demo_messaging", "browser",
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
      name: "New Step",
      type: "open_email",
      application: "demo_email",
      parameters: {},
    };
    setWorkflow((prev) => ({ ...prev, steps: [...prev.steps, newStep] }));
  };

  const removeStep = (idx: number) => {
    setWorkflow((prev) => ({ ...prev, steps: prev.steps.filter((_, i) => i !== idx) }));
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
        body: JSON.stringify({ workflow_definition: workflow }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Save failed (${res.status})`);
      }
      const data = await res.json();
      setSaveMsg(`Saved as: ${data.workflow_id || "workflow"}`);
    } catch (e: unknown) {
      setSaveMsg(`Error: ${e instanceof Error ? e.message : "Save failed"}`);
    } finally {
      setIsSaving(false);
    }
  };

  const handleRunDirect = async () => {
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
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Execute failed (${res.status})`);
      }
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
    <div className="p-6 space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold text-white">Workflow Builder</h2>
          <p className="text-xs text-zinc-500 mt-0.5">Design, configure and test declarative Phase 6 workflows</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleSave}
            disabled={isSaving}
            className="px-3.5 py-1.5 text-xs font-medium rounded-lg bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 text-zinc-200 transition active:scale-95 disabled:opacity-60 cursor-pointer"
          >
            {isSaving ? "Saving…" : "Save Workflow"}
          </button>
          <button
            onClick={handleRunDirect}
            disabled={isRunning || workflow.steps.length === 0}
            className="px-4 py-1.5 text-xs font-semibold rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white transition active:scale-95 disabled:opacity-60 cursor-pointer shadow-md shadow-indigo-950/50"
          >
            {isRunning ? "Running…" : "▶ Test Run"}
          </button>
        </div>
      </div>

      {saveMsg && (
        <div className={`text-xs px-3 py-2 rounded-lg border ${saveMsg.startsWith("Error") ? "bg-rose-950/40 border-rose-800/50 text-rose-300" : "bg-emerald-950/40 border-emerald-800/50 text-emerald-300"}`}>
          {saveMsg}
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
        {/* Left: Workflow metadata */}
        <div className="xl:col-span-1 space-y-4">
          <section className="bg-zinc-900/60 border border-zinc-800/80 rounded-xl p-5">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500 mb-3">Workflow Info</p>
            <div className="space-y-3">
              <div>
                <label className="text-xs text-zinc-400 block mb-1">Name</label>
                <input
                  type="text"
                  value={workflow.name}
                  onChange={(e) => setWorkflow((p) => ({ ...p, name: e.target.value }))}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-1.5 text-xs text-zinc-200 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50 transition"
                />
              </div>
              <div>
                <label className="text-xs text-zinc-400 block mb-1">Description</label>
                <textarea
                  value={workflow.description || ""}
                  onChange={(e) => setWorkflow((p) => ({ ...p, description: e.target.value }))}
                  rows={2}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-1.5 text-xs text-zinc-200 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50 transition resize-none"
                />
              </div>
              <div>
                <label className="text-xs text-zinc-400 block mb-1">Trigger Type</label>
                <select
                  value={workflow.trigger?.type || "manual"}
                  onChange={(e) => setWorkflow((p) => ({ ...p, trigger: { ...p.trigger, type: e.target.value } }))}
                  className="w-full bg-zinc-950 border border-zinc-800 text-zinc-300 text-xs rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-indigo-500 cursor-pointer"
                >
                  <option value="manual">Manual</option>
                  <option value="schedule">Schedule</option>
                  <option value="event">Event</option>
                  <option value="webhook">Webhook</option>
                </select>
              </div>
              <label className="flex items-center gap-2.5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={workflow.requires_approval ?? true}
                  onChange={(e) => setWorkflow((p) => ({ ...p, requires_approval: e.target.checked }))}
                  className="w-3.5 h-3.5 rounded accent-indigo-500"
                />
                <span className="text-xs text-zinc-300">Requires human approval</span>
              </label>
            </div>
          </section>

          {/* Test customer */}
          <section className="bg-zinc-900/60 border border-zinc-800/80 rounded-xl p-5">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500 mb-3">Test Parameters</p>
            <div>
              <label className="text-xs text-zinc-400 block mb-1">Customer Target</label>
              <div className="flex gap-2">
                {["Rahul", "Unknown Customer"].map((name) => (
                  <button
                    key={name}
                    onClick={() => setTestCustomer(name)}
                    className={`flex-1 px-2.5 py-1.5 rounded-lg text-xs font-mono font-medium transition cursor-pointer ${
                      testCustomer === name
                        ? name === "Rahul"
                          ? "bg-cyan-700/60 text-cyan-200 border border-cyan-500/60"
                          : "bg-amber-700/60 text-amber-200 border border-amber-500/60"
                        : "bg-zinc-800 text-zinc-400 hover:text-zinc-200 border border-zinc-700"
                    }`}
                  >
                    {name === "Rahul" ? "Rahul ✓" : "Unknown ✗"}
                  </button>
                ))}
              </div>
            </div>
          </section>
        </div>

        {/* Right: Step editor */}
        <div className="xl:col-span-2 space-y-4">
          <section className="bg-zinc-900/60 border border-zinc-800/80 rounded-xl overflow-hidden">
            <div className="px-5 py-3.5 border-b border-zinc-800/60 flex items-center justify-between bg-zinc-900/30">
              <p className="text-sm font-semibold text-white">
                Steps <span className="text-xs text-zinc-500 font-normal">({workflow.steps.length})</span>
              </p>
              <button
                onClick={addStep}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-indigo-900/60 hover:bg-indigo-800/60 border border-indigo-700/50 text-indigo-300 transition cursor-pointer"
              >
                + Add Step
              </button>
            </div>

            {workflow.steps.length === 0 ? (
              <div className="py-12 text-center text-zinc-500 text-sm">
                No steps yet. Click &quot;Add Step&quot; to begin.
              </div>
            ) : (
              <div className="divide-y divide-zinc-800/50">
                {workflow.steps.map((step, idx) => (
                  <div key={idx} className="p-4 space-y-3">
                    <div className="flex items-start gap-3">
                      {/* Order indicator */}
                      <div className="flex flex-col items-center gap-1 pt-1 shrink-0">
                        <span className="w-6 h-6 rounded-full bg-indigo-950 text-indigo-300 border border-indigo-800/60 flex items-center justify-center text-xs font-mono font-bold">
                          {idx + 1}
                        </span>
                        <button onClick={() => moveStep(idx, -1)} disabled={idx === 0} className="text-zinc-600 hover:text-zinc-300 disabled:opacity-20 text-xs cursor-pointer">↑</button>
                        <button onClick={() => moveStep(idx, 1)} disabled={idx === workflow.steps.length - 1} className="text-zinc-600 hover:text-zinc-300 disabled:opacity-20 text-xs cursor-pointer">↓</button>
                      </div>

                      <div className="flex-1 grid grid-cols-2 gap-3">
                        {/* Step name */}
                        <div>
                          <label className="text-[10px] text-zinc-500 block mb-1">Step Name</label>
                          <input
                            type="text"
                            value={step.name}
                            onChange={(e) => updateStep(idx, { name: e.target.value })}
                            className="w-full bg-zinc-950 border border-zinc-800 rounded px-2.5 py-1.5 text-xs text-zinc-200 focus:outline-none focus:border-indigo-500 transition"
                          />
                        </div>
                        {/* Step ID */}
                        <div>
                          <label className="text-[10px] text-zinc-500 block mb-1">Step ID</label>
                          <input
                            type="text"
                            value={step.id}
                            onChange={(e) => updateStep(idx, { id: e.target.value })}
                            className="w-full bg-zinc-950 border border-zinc-800 rounded px-2.5 py-1.5 text-xs text-zinc-400 font-mono focus:outline-none focus:border-indigo-500 transition"
                          />
                        </div>
                        {/* Type */}
                        <div>
                          <label className="text-[10px] text-zinc-500 block mb-1">Action Type</label>
                          <select
                            value={step.type}
                            onChange={(e) => updateStep(idx, { type: e.target.value })}
                            className="w-full bg-zinc-950 border border-zinc-800 text-zinc-300 text-xs rounded px-2.5 py-1.5 focus:outline-none focus:border-indigo-500 cursor-pointer"
                          >
                            {STEP_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
                          </select>
                        </div>
                        {/* Application */}
                        <div>
                          <label className="text-[10px] text-zinc-500 block mb-1">Application</label>
                          <select
                            value={step.application || ""}
                            onChange={(e) => updateStep(idx, { application: e.target.value })}
                            className="w-full bg-zinc-950 border border-zinc-800 text-zinc-300 text-xs rounded px-2.5 py-1.5 focus:outline-none focus:border-indigo-500 cursor-pointer"
                          >
                            <option value="">None</option>
                            {APPLICATIONS.map((a) => <option key={a} value={a}>{a}</option>)}
                          </select>
                        </div>
                      </div>

                      {/* Remove */}
                      <button
                        onClick={() => removeStep(idx)}
                        className="shrink-0 text-zinc-600 hover:text-rose-400 transition text-sm cursor-pointer p-1 mt-1"
                        title="Remove step"
                      >✕</button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>
      </div>

      {/* Run result */}
      {runError && (
        <div className="bg-rose-950/40 border border-rose-800/60 rounded-xl p-4 text-xs text-rose-300">
          <span className="font-semibold">Execution Error: </span>{runError}
        </div>
      )}
      {runResult && !isRunning && (
        <div className={`rounded-xl p-4 border ${
          (runResult.status as string) === "completed" ? "bg-emerald-950/30 border-emerald-700/40"
          : (runResult.status as string) === "paused" ? "bg-amber-950/30 border-amber-700/40"
          : "bg-rose-950/30 border-rose-700/40"
        }`}>
          <p className={`text-sm font-semibold mb-1 ${
            (runResult.status as string) === "completed" ? "text-emerald-300"
            : (runResult.status as string) === "paused" ? "text-amber-300"
            : "text-rose-300"
          }`}>
            Run {String(runResult.status).charAt(0).toUpperCase() + String(runResult.status).slice(1)}
          </p>
          <p className="text-xs text-zinc-400">
            {runResult.completed_actions as number || 0} of {runResult.total_actions as number || 0} actions completed
            {runResult.execution_time_seconds ? ` in ${runResult.execution_time_seconds as number}s` : ""}
          </p>
        </div>
      )}
    </div>
  );
}
