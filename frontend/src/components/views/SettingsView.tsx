"use client";

import React from "react";
import { API_BASE_URL } from "@/lib/utils";

export default function SettingsView() {
  return (
    <div className="p-6 space-y-6 max-w-2xl">
      <div>
        <h2 className="text-base font-semibold text-white">Settings</h2>
        <p className="text-xs text-zinc-500 mt-0.5">System configuration and agent preferences</p>
      </div>

      {/* API Endpoint */}
      <section className="bg-zinc-900/60 border border-zinc-800/80 rounded-xl p-5 space-y-4">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">Backend Connection</p>
        <div>
          <label className="text-xs text-zinc-400 block mb-1">API Base URL</label>
          <div className="flex items-center gap-2">
            <input
              type="text"
              readOnly
              value={API_BASE_URL}
              className="flex-1 bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-1.5 text-xs text-zinc-300 font-mono focus:outline-none cursor-default select-all"
            />
            <span className="text-[10px] text-zinc-600">NEXT_PUBLIC_API_URL</span>
          </div>
          <p className="text-[11px] text-zinc-600 mt-1">Set via environment variable in <code className="text-zinc-500">.env.local</code>.</p>
        </div>
      </section>

      {/* Phase info */}
      <section className="bg-zinc-900/60 border border-zinc-800/80 rounded-xl p-5 space-y-3">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">Phase Status</p>
        <div className="space-y-2">
          {[
            { phase: "Phase 1", label: "Observational Event Ingestion", status: "complete" },
            { phase: "Phase 2", label: "Workflow Discovery (Repeated Pattern Detection)", status: "complete" },
            { phase: "Phase 3", label: "AI Workflow Understanding (Gemini)", status: "complete" },
            { phase: "Phase 4.1–4.6", label: "Automation Execution + Human-in-the-Loop", status: "complete" },
            { phase: "Phase 5", label: "Real Desktop Activity Agent (macOS)", status: "complete" },
            { phase: "Phase 6", label: "Generalized Workflow Engine + Frontend Redesign", status: "active" },
          ].map(({ phase, label, status }) => (
            <div key={phase} className="flex items-center gap-3 text-xs">
              <span className={`w-2 h-2 rounded-full shrink-0 ${status === "active" ? "bg-cyan-400 animate-pulse" : "bg-emerald-500"}`} />
              <span className="font-mono text-zinc-500 w-28 shrink-0">{phase}</span>
              <span className="text-zinc-300">{label}</span>
              <span className={`ml-auto text-[10px] font-semibold ${status === "active" ? "text-cyan-400" : "text-emerald-400"}`}>
                {status === "active" ? "Active" : "Complete"}
              </span>
            </div>
          ))}
        </div>
      </section>

      {/* Useful commands */}
      <section className="bg-zinc-900/60 border border-zinc-800/80 rounded-xl p-5 space-y-3">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">Useful Commands</p>
        <div className="space-y-2">
          {[
            { label: "Seed test events", cmd: "python backend/test_event.py --all" },
            { label: "Seed workflow patterns", cmd: "python backend/test_event.py --seed-workflows" },
            { label: "Start backend", cmd: "cd backend && uvicorn app:app --reload" },
            { label: "Start desktop agent", cmd: "python -m agent run" },
            { label: "Run backend tests", cmd: ".venv/bin/python3 -m pytest backend/ -v" },
          ].map(({ label, cmd }) => (
            <div key={cmd} className="space-y-1">
              <p className="text-[10px] text-zinc-500">{label}</p>
              <code className="block text-xs font-mono text-indigo-300 bg-zinc-950 border border-zinc-800 rounded px-3 py-1.5 select-all">
                {cmd}
              </code>
            </div>
          ))}
        </div>
      </section>

      {/* Privacy note */}
      <section className="bg-zinc-900/60 border border-zinc-800/80 rounded-xl p-5">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500 mb-2">Privacy</p>
        <p className="text-xs text-zinc-400 leading-relaxed">
          The desktop agent (Phase 5) uses macOS NSWorkspace APIs for opt-in application focus tracking only.
          No keystrokes, clipboard, or screen content is captured. Activity is stored locally in MongoDB Atlas
          and never shared externally. All automation runs locally via PlaywrightExecutor with no cloud
          browser sessions.
        </p>
      </section>
    </div>
  );
}
