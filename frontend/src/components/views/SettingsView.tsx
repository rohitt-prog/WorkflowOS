"use client";

import React, { useState } from "react";
import { API_BASE_URL } from "@/lib/utils";

export default function SettingsView() {
  const [copiedCmd, setCopiedCmd] = useState<string | null>(null);

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedCmd(text);
    setTimeout(() => setCopiedCmd(null), 2000);
  };

  return (
    <div className="p-6 space-y-6 max-w-3xl mx-auto bg-[#F7F9FC]">
      {/* View Header */}
      <div className="bg-white border border-[#E2E8F0] rounded-xl p-5 shadow-2xs">
        <h2 className="text-base font-bold text-[#0F172A] tracking-tight">
          System Preferences & Configuration
        </h2>
        <p className="text-xs text-[#64748B] mt-0.5">
          Backend API configuration, agent operational parameters, and phase readiness checklist.
        </p>
      </div>

      {/* API Endpoint Section */}
      <section className="bg-white border border-[#E2E8F0] rounded-xl p-5 space-y-4 shadow-2xs">
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-[#64748B]">
            Backend Connection
          </h3>
          <p className="text-xs text-[#475569] mt-0.5">
            Active REST API endpoint targeted by the WorkFlowOS frontend.
          </p>
        </div>

        <div>
          <label className="text-xs font-semibold text-[#0F172A] block mb-1">
            API Base URL
          </label>
          <div className="flex items-center gap-2">
            <input
              type="text"
              readOnly
              value={API_BASE_URL}
              className="flex-1 bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg px-3 py-2 text-xs text-[#0F172A] font-mono focus:outline-none cursor-default select-all"
            />
            <span className="text-[11px] font-mono text-[#94A3B8] px-2 py-1 rounded bg-[#F1F5F9] border border-[#E2E8F0]">
              NEXT_PUBLIC_API_URL
            </span>
          </div>
          <p className="text-[11px] text-[#64748B] mt-1.5">
            Configured locally via <code className="text-[#0F172A] font-mono bg-[#F1F5F9] px-1 py-0.5 rounded">.env.local</code>.
          </p>
        </div>
      </section>

      {/* Phase Info Status */}
      <section className="bg-white border border-[#E2E8F0] rounded-xl p-5 space-y-4 shadow-2xs">
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-[#64748B]">
            Platform Milestones & Architecture
          </h3>
          <p className="text-xs text-[#475569] mt-0.5">
            Architectural layers completed and verified in the current WorkFlowOS build.
          </p>
        </div>

        <div className="divide-y divide-[#E2E8F0] border border-[#E2E8F0] rounded-xl overflow-hidden">
          {[
            { phase: "Phase 1", label: "Observational Event Ingestion & MongoDB Atlas", status: "complete" },
            { phase: "Phase 2", label: "Algorithmic Workflow Discovery (Repetition Scanner)", status: "complete" },
            { phase: "Phase 3", label: "AI Workflow Understanding & Gemini SDK Proposal Engine", status: "complete" },
            { phase: "Phase 4", label: "Playwright Automation Execution + Human Approval Gate", status: "complete" },
            { phase: "Phase 5", label: "Real macOS Desktop Activity Agent (NSWorkspace Native)", status: "complete" },
            { phase: "Phase 6", label: "Declarative Workflow Engine & Modern Light UI Redesign", status: "complete" },
          ].map(({ phase, label }) => (
            <div key={phase} className="flex items-center justify-between p-3 text-xs bg-white hover:bg-[#F8FAFC] transition">
              <div className="flex items-center gap-3">
                <span className="w-2 h-2 rounded-full bg-[#16A34A] shrink-0" />
                <span className="font-mono font-bold text-[#0F172A] w-24 shrink-0">{phase}</span>
                <span className="text-[#475569]">{label}</span>
              </div>
              <span className="text-[10px] font-semibold uppercase px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 shrink-0">
                Verified
              </span>
            </div>
          ))}
        </div>
      </section>

      {/* Useful Commands Section */}
      <section className="bg-white border border-[#E2E8F0] rounded-xl p-5 space-y-4 shadow-2xs">
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-[#64748B]">
            Operational CLI Commands
          </h3>
          <p className="text-xs text-[#475569] mt-0.5">
            Standard development and agent control commands.
          </p>
        </div>

        <div className="space-y-2.5">
          {[
            { label: "Start macOS Activity Agent", cmd: "python -m agent run" },
            { label: "Inspect Desktop Agent Status", cmd: "python -m agent status" },
            { label: "Run All Test Suites (Phases 1–6)", cmd: ".venv/bin/python3 -m unittest discover -s backend -p 'test_phase*.py'" },
            { label: "Start FastAPI Backend", cmd: "uvicorn backend.main:app --reload --port 8000" },
          ].map(({ label, cmd }) => (
            <div key={cmd} className="space-y-1">
              <span className="text-[11px] font-medium text-[#64748B] block">{label}</span>
              <div className="flex items-center gap-2">
                <code className="flex-1 text-xs font-mono text-[#0F172A] bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg px-3 py-2 select-all">
                  {cmd}
                </code>
                <button
                  onClick={() => copyToClipboard(cmd)}
                  className="px-2.5 py-2 text-xs font-medium rounded-lg bg-white border border-[#E2E8F0] text-[#0F172A] hover:bg-[#F8FAFC] shadow-2xs transition cursor-pointer shrink-0"
                >
                  {copiedCmd === cmd ? "Copied!" : "Copy"}
                </button>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Privacy Guarantee Card */}
      <section className="bg-white border border-[#E2E8F0] rounded-xl p-5 shadow-2xs space-y-2">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-[#64748B]">
          Privacy & Local Security Guarantee
        </h3>
        <p className="text-xs text-[#475569] leading-relaxed">
          The Phase 5 desktop agent uses Apple macOS native NSWorkspace APIs strictly for application activation tracking.
          It never captures keystrokes, passwords, clipboard data, or screen pixels. All captured telemetry remains in your
          local MongoDB Atlas cluster and is executed locally via Playwright with explicit operator approval.
        </p>
      </section>
    </div>
  );
}
