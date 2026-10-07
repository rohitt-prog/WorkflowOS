"use client";

import React, { useState } from "react";
import {
  ActivityEvent,
  AutomationExecutionRecord,
  DiscoveryResult,
  SystemStatusResponse,
  ViewId,
} from "@/lib/types";
import {
  formatEventStep,
  statusBadgeConfig,
  getApplicationDisplayName,
  getAppBadgeClass,
  formatTimestamp,
} from "@/lib/utils";

interface DashboardViewProps {
  events: ActivityEvent[];
  executions: AutomationExecutionRecord[];
  discovery: DiscoveryResult | null;
  systemStatus: SystemStatusResponse | null;
  loading: boolean;
  historyLoading: boolean;
  onNavigate: (view: ViewId) => void;
  onRefresh?: () => void;
}

export default function DashboardView({
  events,
  executions,
  discovery,
  systemStatus,
  loading,
  historyLoading,
  onNavigate,
  onRefresh,
}: DashboardViewProps) {
  const [showOnboarding, setShowOnboarding] = useState(true);

  // Derived metrics from real data
  const completedExecs = executions.filter(
    (e) => e.status === "completed"
  ).length;
  const connectedAppsCount = systemStatus?.applications?.connected ?? 0;
  const availableAppsCount = systemStatus?.applications?.available ?? 3;
  const discoveredCount =
    discovery?.workflows?.length ?? systemStatus?.workflows?.discovered ?? 0;
  const agentStatus = systemStatus?.agent ?? "disconnected";

  const recentEvents = events.slice(0, 6);
  const recentExecutions = executions.slice(0, 5);

  return (
    <div className="space-y-6 p-6 max-w-7xl mx-auto">
      {/* Product Banner & System Posture */}
      <div className="bg-white border border-[#E2E8F0] rounded-xl p-5 shadow-2xs">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold uppercase tracking-wider text-[#2563EB]">
                WorkFlowOS Platform
              </span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
                Phase 14 Productized
              </span>
            </div>
            <h2 className="text-xl font-bold text-[#0F172A] tracking-tight mt-1">
              Intelligent Automation Dashboard
            </h2>
            <p className="text-xs text-[#64748B] mt-0.5 max-w-2xl">
              Unified operational view across desktop observation, pattern discovery,
              adaptive learning, and human-in-the-loop automation.
            </p>
          </div>
          <div className="flex items-center gap-2.5 shrink-0">
            <button
              onClick={() => onNavigate("workflows")}
              className="px-3.5 py-2 text-xs font-semibold rounded-lg bg-white border border-[#E2E8F0] hover:bg-[#F8FAFC] hover:shadow-xs text-[#0F172A] shadow-2xs transition-all duration-150 active:translate-y-px cursor-pointer"
            >
              Explore Workflows ({discoveredCount})
            </button>
            <button
              onClick={() => onNavigate("applications")}
              className="px-3.5 py-2 text-xs font-semibold rounded-lg bg-[#2563EB] hover:bg-[#1D4ED8] hover:shadow-xs text-white shadow-2xs transition-all duration-150 active:translate-y-px cursor-pointer"
            >
              Applications Ecosystem
            </button>
          </div>
        </div>

        {/* Complete Lifecycle Stepper (Section 3) */}
        <div className="mt-5 pt-4 border-t border-[#F1F5F9]">
          <div className="text-[10px] font-semibold uppercase tracking-wider text-[#94A3B8] mb-2.5">
            WorkFlowOS Closed-Loop Lifecycle
          </div>
          <div className="grid grid-cols-3 sm:grid-cols-5 md:grid-cols-9 gap-1.5 text-center text-[11px] font-mono">
            {[
              { step: "OBSERVE", sub: "Desktop NSWorkspace" },
              { step: "UNDERSTAND", sub: "Semantic intent" },
              { step: "DISCOVER", sub: "Pattern detection" },
              { step: "LEARN", sub: "Feedback loop" },
              { step: "PLAN", sub: "Strategy selection" },
              { step: "APPROVE", sub: "Human-in-the-loop" },
              { step: "AUTOMATE", sub: "Safe execution" },
              { step: "EVALUATE", sub: "Empirical outcomes" },
              { step: "LEARN", sub: "Adaptive weights" },
            ].map((item, idx) => (
              <div
                key={idx}
                className="p-2 rounded-lg bg-[#F8FAFC] border border-[#E2E8F0] flex flex-col justify-center"
              >
                <span className="font-bold text-[#0F172A] text-[10px]">
                  {item.step}
                </span>
                <span className="text-[9px] text-[#94A3B8] truncate">
                  {item.sub}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* High-Level Status Cards (Section 5) */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3.5">
        {/* 1. System Status */}
        <div className="bg-white border border-[#E2E8F0] rounded-xl p-4 shadow-2xs flex flex-col justify-between">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-[#64748B]">
            System Status
          </span>
          <div className="my-2">
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-sm font-bold text-[#0F172A]">Operational</span>
            </div>
            <p className="text-[10px] text-[#64748B] mt-0.5">FastAPI & MongoDB</p>
          </div>
        </div>

        {/* 2. Agent Status */}
        <div className="bg-white border border-[#E2E8F0] rounded-xl p-4 shadow-2xs flex flex-col justify-between">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-[#64748B]">
            Desktop Agent
          </span>
          <div className="my-2">
            <div className="flex items-center gap-1.5">
              <span
                className={`w-2 h-2 rounded-full ${
                  agentStatus === "connected"
                    ? "bg-emerald-500 animate-pulse"
                    : agentStatus === "degraded"
                    ? "bg-amber-500"
                    : "bg-slate-400"
                }`}
              />
              <span className="text-sm font-bold text-[#0F172A] capitalize">
                {agentStatus === "connected"
                  ? "Connected"
                  : agentStatus === "degraded"
                  ? "Degraded"
                  : "Disconnected"}
              </span>
            </div>
            <p className="text-[10px] text-[#64748B] mt-0.5 truncate">
              {agentStatus === "connected"
                ? "Streaming events"
                : "python -m agent run"}
            </p>
          </div>
        </div>

        {/* 3. Applications */}
        <div className="bg-white border border-[#E2E8F0] rounded-xl p-4 shadow-2xs flex flex-col justify-between">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-[#64748B]">
            Applications
          </span>
          <div className="my-2">
            <div className="text-lg font-bold font-mono text-[#0F172A]">
              {loading ? "…" : `${connectedAppsCount} Connected`}
            </div>
            <p className="text-[10px] text-[#64748B] mt-0.5">
              {availableAppsCount} registered in ecosystem
            </p>
          </div>
        </div>

        {/* 4. Workflows */}
        <div className="bg-white border border-[#E2E8F0] rounded-xl p-4 shadow-2xs flex flex-col justify-between">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-[#64748B]">
            Workflows
          </span>
          <div className="my-2">
            <div className="text-lg font-bold font-mono text-[#0F172A]">
              {loading ? "…" : `${discoveredCount} Discovered`}
            </div>
            <p className="text-[10px] text-[#64748B] mt-0.5">
              {discoveredCount > 0 ? "Repetition detected" : "Observing traffic"}
            </p>
          </div>
        </div>

        {/* 5. Automations */}
        <div className="bg-white border border-[#E2E8F0] rounded-xl p-4 shadow-2xs flex flex-col justify-between">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-[#64748B]">
            Automations
          </span>
          <div className="my-2">
            <div className="text-lg font-bold font-mono text-[#0F172A]">
              {historyLoading ? "…" : `${completedExecs} Successful`}
            </div>
            <p className="text-[10px] text-[#64748B] mt-0.5">
              {executions.length} total runs logged
            </p>
          </div>
        </div>

        {/* 6. Privacy */}
        <div className="bg-white border border-[#E2E8F0] rounded-xl p-4 shadow-2xs flex flex-col justify-between">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-[#64748B]">
            Privacy & Safety
          </span>
          <div className="my-2">
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-500" />
              <span className="text-sm font-bold text-[#0F172A]">Protected</span>
            </div>
            <p className="text-[10px] text-[#64748B] mt-0.5">
              Redaction & Approval Gate
            </p>
          </div>
        </div>
      </div>

      {/* Lightweight First-Run Onboarding Guide (Section 15) */}
      {showOnboarding && (
        <section className="bg-white border border-[#BFDBFE] rounded-xl p-5 shadow-2xs relative">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-bold text-[#0F172A]">
                  Welcome to WorkFlowOS
                </h3>
                <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200">
                  Ready to Start
                </span>
              </div>
              <p className="text-xs text-[#64748B] mt-1 max-w-2xl leading-relaxed">
                WorkFlowOS observes repetitive digital work, discovers workflows, and
                helps automate them safely. Check the operational readiness below:
              </p>
            </div>
            <button
              onClick={() => setShowOnboarding(false)}
              className="text-[#94A3B8] hover:text-[#0F172A] text-xs cursor-pointer p-1 rounded"
              title="Dismiss onboarding"
            >
              ✕
            </button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 mt-4 pt-4 border-t border-[#EFF6FF]">
            <div className="bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg p-3">
              <div className="flex items-center gap-2 text-xs font-semibold text-[#0F172A]">
                <span className="text-emerald-600 font-bold">✓</span>
                <span>1. Activity Agent</span>
              </div>
              <p className="text-[11px] text-[#64748B] mt-1">
                {agentStatus === "connected"
                  ? "Connected & actively capturing focus events."
                  : "Ready. Run `python -m agent run` to stream macOS activity."}
              </p>
            </div>

            <div className="bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg p-3">
              <div className="flex items-center gap-2 text-xs font-semibold text-[#0F172A]">
                <span className="text-emerald-600 font-bold">✓</span>
                <span>2. Backend Engine</span>
              </div>
              <p className="text-[11px] text-[#64748B] mt-1">
                Connected. MongoDB Atlas event stream and REST API active on port 8000.
              </p>
            </div>

            <div className="bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg p-3">
              <div className="flex items-center gap-2 text-xs font-semibold text-[#0F172A]">
                <span className="text-emerald-600 font-bold">✓</span>
                <span>3. Applications</span>
              </div>
              <p className="text-[11px] text-[#64748B] mt-1">
                {availableAppsCount} available adapters (Email, CRM, Chat, Gmail) ready in registry.
              </p>
            </div>

            <div className="bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg p-3">
              <div className="flex items-center gap-2 text-xs font-semibold text-[#0F172A]">
                <span className="text-emerald-600 font-bold">✓</span>
                <span>4. Privacy & Safety</span>
              </div>
              <p className="text-[11px] text-[#64748B] mt-1">
                Protected. Keylogging and screenshots disabled. Mutating actions require approval.
              </p>
            </div>
          </div>
        </section>
      )}

      {/* Main Two-Column View: Recent Activity & Recent Executions */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Activity Table (Section 6) */}
        <section className="bg-white border border-[#E2E8F0] rounded-xl p-5 shadow-2xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-3">
              <div>
                <h3 className="text-xs font-semibold uppercase tracking-wider text-[#64748B]">
                  Recent Activity
                </h3>
                <p className="text-[11px] text-[#64748B] mt-0.5">
                  Latest observed actions captured from desktop and demo applications
                </p>
              </div>
              <div className="flex items-center gap-2">
                {onRefresh && (
                  <button
                    onClick={onRefresh}
                    className="text-[11px] text-[#2563EB] hover:text-[#1D4ED8] font-medium cursor-pointer"
                  >
                    Refresh
                  </button>
                )}
                <button
                  onClick={() => onNavigate("activity")}
                  className="text-[11px] text-[#2563EB] hover:text-[#1D4ED8] font-semibold cursor-pointer"
                >
                  View All ({events.length}) →
                </button>
              </div>
            </div>

            {loading ? (
              <div className="py-8 text-center text-xs text-[#94A3B8]">
                Loading recent activity…
              </div>
            ) : recentEvents.length === 0 ? (
              <div className="py-8 text-center text-xs text-[#94A3B8] border border-dashed border-[#E2E8F0] rounded-xl">
                No activity captured yet.
                <p className="text-[11px] text-[#64748B] mt-1">
                  Start `python -m agent run` or trigger actions in the Demo Applications.
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-[#F8FAFC] text-[#64748B] border-b border-[#E2E8F0]">
                    <tr>
                      <th className="py-2.5 px-3 whitespace-nowrap">Application</th>
                      <th className="py-2.5 px-3 whitespace-nowrap">Action</th>
                      <th className="py-2.5 px-3 whitespace-nowrap">Time</th>
                      <th className="py-2.5 px-3 whitespace-nowrap">Target</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#E2E8F0]">
                    {recentEvents.map((ev) => {
                      const t = formatTimestamp(ev.timestamp);
                      const badgeClass = getAppBadgeClass(ev.application);
                      return (
                        <tr key={ev.id} className="hover:bg-[#F8FAFC] transition">
                          <td className="py-2.5 px-3 whitespace-nowrap">
                            <span
                              className={`text-[10px] font-medium px-2 py-0.5 rounded border ${badgeClass}`}
                            >
                              {getApplicationDisplayName(ev.application)}
                            </span>
                          </td>
                          <td className="py-2.5 px-3 font-mono font-medium text-[#0F172A] whitespace-nowrap">
                            {formatEventStep(ev.event_type)}
                          </td>
                          <td className="py-2.5 px-3 font-mono text-[#64748B] whitespace-nowrap">
                            {t.relative || t.full}
                          </td>
                          <td className="py-2.5 px-3 text-[#64748B] max-w-48 truncate">
                            {ev.target || "—"}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </section>

        {/* Recent Executions History (Section 10) */}
        <section className="bg-white border border-[#E2E8F0] rounded-xl p-5 shadow-2xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-3">
              <div>
                <h3 className="text-xs font-semibold uppercase tracking-wider text-[#64748B]">
                  Recent Executions
                </h3>
                <p className="text-[11px] text-[#64748B] mt-0.5">
                  Automated workflow runs, outcomes, and intervention status
                </p>
              </div>
              <button
                onClick={() => onNavigate("executions")}
                className="text-[11px] text-[#2563EB] hover:text-[#1D4ED8] font-semibold cursor-pointer"
              >
                View History ({executions.length}) →
              </button>
            </div>

            {historyLoading ? (
              <div className="py-8 text-center text-xs text-[#94A3B8]">
                Loading execution history…
              </div>
            ) : recentExecutions.length === 0 ? (
              <div className="py-8 text-center text-xs text-[#94A3B8] border border-dashed border-[#E2E8F0] rounded-xl">
                No automated executions logged yet.
                <p className="text-[11px] text-[#64748B] mt-1">
                  Approve and run a discovered or declarative workflow to record execution history.
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-[#F8FAFC] text-[#64748B] border-b border-[#E2E8F0]">
                    <tr>
                      <th className="py-2.5 px-3 whitespace-nowrap">Workflow</th>
                      <th className="py-2.5 px-3 whitespace-nowrap">Status</th>
                      <th className="py-2.5 px-3 whitespace-nowrap">Progress</th>
                      <th className="py-2.5 px-3 whitespace-nowrap text-right">Time</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#E2E8F0]">
                    {recentExecutions.map((rec) => {
                      const cfg = statusBadgeConfig(rec.status);
                      const t = rec.completed_at
                        ? formatTimestamp(rec.completed_at)
                        : rec.started_at
                        ? formatTimestamp(rec.started_at)
                        : null;
                      return (
                        <tr key={rec.execution_id} className="hover:bg-[#F8FAFC] transition">
                          <td className="py-2.5 px-3 font-medium text-[#0F172A] max-w-44 truncate">
                            {rec.workflow_name || "Automation Workflow"}
                          </td>
                          <td className="py-2.5 px-3 whitespace-nowrap">
                            <span
                              className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${cfg.className}`}
                            >
                              {cfg.label}
                            </span>
                          </td>
                          <td className="py-2.5 px-3 whitespace-nowrap font-mono text-[#64748B]">
                            {rec.completed_actions?.length ?? 0}/{rec.total_actions ?? 0} steps
                          </td>
                          <td className="py-2.5 px-3 font-mono text-[#94A3B8] text-right whitespace-nowrap">
                            {t ? t.relative || t.full : "—"}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
