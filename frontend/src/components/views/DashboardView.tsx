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
  getApplicationDisplayName,
  getAppBadgeClass,
  formatTimestamp,
  getActionDisplayLabel,
} from "@/lib/utils";
import { ExecutionDetailModal } from "./ExecutionsView";

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

// 9-step closed-loop lifecycle configuration
const LIFECYCLE_STEPS = [
  {
    step: "OBSERVE",
    sub: "Desktop NSWorkspace",
    detail: "Observes desktop windows, focus changes, and user interaction stream",
    icon: (
      <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.964-7.178z" />
        <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
    ),
  },
  {
    step: "UNDERSTAND",
    sub: "Semantic intent",
    detail: "Parses target applications, UI contexts, and user input intent",
    icon: (
      <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
      </svg>
    ),
  },
  {
    step: "DISCOVER",
    sub: "Pattern detection",
    detail: "Identifies recurrent multi-step workflow candidate sequences",
    icon: (
      <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
      </svg>
    ),
  },
  {
    step: "LEARN",
    sub: "Feedback loop",
    detail: "Evaluates cross-session consistency, support, and noise bounds",
    icon: (
      <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 18L9 11.25l4.306 4.307a11.95 11.95 0 015.814-5.519l2.74-1.22m0 0l-5.94-2.28m5.94 2.28l-2.28 5.941" />
      </svg>
    ),
  },
  {
    step: "PLAN",
    sub: "Strategy selection",
    detail: "Synthesizes executable action graphs and execution strategies",
    icon: (
      <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 6.75h12M8.25 12h12m-12 5.25h12M3.75 6.75h.007v.008H3.75V6.75zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zM3.75 12h.007v.008H3.75V12zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm-.375 5.25h.007v.008H3.75v-.008zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0z" />
      </svg>
    ),
  },
  {
    step: "APPROVE",
    sub: "Human-in-the-loop",
    detail: "Enforces explicit user authorization before any mutating action",
    icon: (
      <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
      </svg>
    ),
  },
  {
    step: "AUTOMATE",
    sub: "Safe execution",
    detail: "Executes approved steps through adapter APIs and Playwright drivers",
    icon: (
      <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.348a1.125 1.125 0 010 1.971l-11.54 6.347a1.125 1.125 0 01-1.667-.985V5.653z" />
      </svg>
    ),
  },
  {
    step: "EVALUATE",
    sub: "Empirical outcomes",
    detail: "Monitors step results, runtime telemetry, and user overrides",
    icon: (
      <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
  },
  {
    step: "LEARN",
    sub: "Adaptive weights",
    detail: "Refines ranking heuristics and strategy selection based on results",
    icon: (
      <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" />
      </svg>
    ),
  },
];

// Execution status indicator helpers
function getExecutionStatusBadge(status: string) {
  switch (status.toLowerCase()) {
    case "completed":
      return {
        symbol: "✓",
        label: "Completed",
        badgeClass: "bg-emerald-50 text-emerald-700 border-emerald-200",
        dotClass: "bg-emerald-600",
      };
    case "paused":
      return {
        symbol: "!",
        label: "Paused",
        badgeClass: "bg-amber-50 text-amber-700 border-amber-200",
        dotClass: "bg-amber-500",
      };
    case "failed":
      return {
        symbol: "×",
        label: "Failed",
        badgeClass: "bg-rose-50 text-rose-700 border-rose-200",
        dotClass: "bg-rose-600",
      };
    case "cancelled":
      return {
        symbol: "○",
        label: "Cancelled",
        badgeClass: "bg-slate-100 text-slate-700 border-slate-200",
        dotClass: "bg-slate-500",
      };
    case "running":
      return {
        symbol: "⟳",
        label: "Running",
        badgeClass: "bg-blue-50 text-blue-700 border-blue-200",
        dotClass: "bg-blue-600",
      };
    default:
      return {
        symbol: "•",
        label: status,
        badgeClass: "bg-slate-100 text-slate-700 border-slate-200",
        dotClass: "bg-slate-400",
      };
  }
}

// Compute duration string from execution timestamps
function getExecutionDuration(rec: AutomationExecutionRecord): string {
  if (!rec.started_at) return "—";
  const start = new Date(rec.started_at).getTime();
  const end = rec.completed_at ? new Date(rec.completed_at).getTime() : Date.now();
  if (isNaN(start) || isNaN(end) || end < start) return "—";
  const sec = Math.round((end - start) / 1000);
  if (sec < 60) return `${sec}s`;
  const min = Math.floor(sec / 60);
  const remSec = sec % 60;
  return `${min}m ${remSec}s`;
}

// Application status dot color helper
function getAppDotColor(app: string): string {
  const lower = (app || "").toLowerCase();
  if (lower.includes("gmail") || lower.includes("mail") || lower.includes("email")) {
    return "bg-purple-500";
  }
  if (lower.includes("crm")) {
    return "bg-sky-500";
  }
  if (lower.includes("chat") || lower.includes("message")) {
    return "bg-emerald-500";
  }
  if (lower.includes("browser") || lower.includes("web")) {
    return "bg-amber-500";
  }
  return "bg-slate-400";
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
  const [selectedExecution, setSelectedExecution] =
    useState<AutomationExecutionRecord | null>(null);

  // Derived metrics from real API data
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

  // Highest-ranked / recommended workflow
  const topWorkflow =
    discovery?.workflows && discovery.workflows.length > 0
      ? discovery.workflows[0]
      : null;

  return (
    <div className="space-y-6 p-6 max-w-7xl mx-auto">
      {/* ==================================================
          1. HERO COMMAND CENTER (Section 6)
          ================================================== */}
      <div className="bg-white border border-[#E2E8F0] rounded-xl p-6 shadow-2xs">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-5">
          <div>
            <div className="flex items-center gap-2.5 flex-wrap">
              <span className="text-xs font-bold uppercase tracking-wider text-[#2563EB]">
                WorkFlowOS Platform
              </span>
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                System Operational
              </span>
            </div>
            <h2 className="text-2xl font-bold text-[#0F172A] tracking-tight mt-1.5">
              Intelligent Automation Dashboard
            </h2>
            <p className="text-xs sm:text-sm text-[#64748B] mt-1 max-w-2xl leading-relaxed">
              Observe repetitive work. Discover workflows. Automate them safely.
            </p>
          </div>

          <div className="flex items-center gap-2.5 shrink-0 flex-wrap">
            <button
              onClick={() => onNavigate("workflows")}
              className="px-4 py-2 text-xs font-semibold rounded-lg bg-white border border-[#E2E8F0] hover:bg-[#F8FAFC] text-[#0F172A] shadow-2xs transition-colors duration-150 cursor-pointer"
            >
              Explore Workflows ({discoveredCount})
            </button>
            <button
              onClick={() => onNavigate("applications")}
              className="px-4 py-2 text-xs font-semibold rounded-lg bg-[#2563EB] hover:bg-[#1D4ED8] text-white shadow-2xs transition-colors duration-150 cursor-pointer"
            >
              Applications Ecosystem
            </button>
            {onRefresh && (
              <button
                onClick={onRefresh}
                title="Refresh dashboard metrics"
                className="p-2 text-xs rounded-lg bg-white border border-[#E2E8F0] hover:bg-[#F8FAFC] text-[#64748B] hover:text-[#0F172A] shadow-2xs transition-colors duration-150 cursor-pointer"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
              </button>
            )}
          </div>
        </div>

        {/* ==================================================
            2. WORKFLOW LIFECYCLE (Section 7)
            ================================================== */}
        <div className="mt-6 pt-5 border-t border-[#F1F5F9]">
          <div className="flex items-center justify-between mb-3">
            <span className="text-[10px] font-bold uppercase tracking-wider text-[#94A3B8]">
              WorkFlowOS Closed-Loop Lifecycle
            </span>
            <span className="text-[10px] font-mono text-[#94A3B8]">
              9 Canonical Stages
            </span>
          </div>

          <div className="grid grid-cols-3 sm:grid-cols-5 lg:grid-cols-9 gap-2">
            {LIFECYCLE_STEPS.map((item, idx) => (
              <div
                key={idx}
                title={item.detail}
                className="group relative p-2.5 rounded-lg bg-[#F8FAFC] hover:bg-white border border-[#E2E8F0] hover:border-[#CBD5E1] transition-colors duration-150 flex flex-col justify-between cursor-default"
              >
                <div className="flex items-center justify-between gap-1 text-[#64748B] group-hover:text-[#2563EB] transition-colors duration-150">
                  <span className="text-[9px] font-mono text-[#94A3B8]">
                    0{idx + 1}
                  </span>
                  <span>{item.icon}</span>
                </div>
                <div className="mt-2">
                  <div className="font-bold text-[#0F172A] text-[10px] tracking-tight">
                    {item.step}
                  </div>
                  <div className="text-[9px] text-[#64748B] truncate mt-0.5">
                    {item.sub}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ==================================================
          3. STAT CARDS WITH CLEAR HIERARCHY (Section 8)
          ================================================== */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3.5">
        {/* Card 1: System Status */}
        <div className="bg-white border border-[#E2E8F0] rounded-xl p-4 shadow-2xs flex flex-col justify-between">
          <div className="flex items-center justify-between text-[#64748B]">
            <span className="text-[10px] font-bold uppercase tracking-wider text-[#64748B]">
              System Status
            </span>
            <svg className="w-3.5 h-3.5 text-[#94A3B8]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M5.25 14.25h13.5m-13.5 0a3 3 0 01-3-3m3 3a3 3 0 100 6h13.5a3 3 0 100-6m-16.5-3a3 3 0 013-3h13.5a3 3 0 013 3m-19.5 0a4.5 4.5 0 01.9-2.7L5.7 7.05a4.5 4.5 0 013.6-1.8h5.4a4.5 4.5 0 013.6 1.8l2.55 4.5a4.5 4.5 0 01.9 2.7" />
            </svg>
          </div>
          <div className="my-2.5">
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-500" />
              <span className="text-lg font-bold text-[#0F172A] leading-tight">
                Operational
              </span>
            </div>
            <p className="text-[11px] text-[#64748B] mt-0.5 truncate">
              FastAPI & MongoDB active
            </p>
          </div>
        </div>

        {/* Card 2: Desktop Agent */}
        <div className="bg-white border border-[#E2E8F0] rounded-xl p-4 shadow-2xs flex flex-col justify-between">
          <div className="flex items-center justify-between text-[#64748B]">
            <span className="text-[10px] font-bold uppercase tracking-wider text-[#64748B]">
              Desktop Agent
            </span>
            <svg className="w-3.5 h-3.5 text-[#94A3B8]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 17.25v1.007a3 3 0 01-.879 2.122L7.5 21h9l-.621-.621A3 3 0 0115 18.257V17.25m6-12V15a2.25 2.25 0 01-2.25 2.25H5.25A2.25 2.25 0 013 15V5.25m18 0A2.25 2.25 0 0018.75 3H5.25A2.25 2.25 0 003 5.25m18 0H3" />
            </svg>
          </div>
          <div className="my-2.5">
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
              <span className="text-lg font-bold text-[#0F172A] capitalize leading-tight">
                {agentStatus === "connected"
                  ? "Connected"
                  : agentStatus === "degraded"
                  ? "Degraded"
                  : "Standby"}
              </span>
            </div>
            <p className="text-[11px] text-[#64748B] mt-0.5 truncate">
              {agentStatus === "connected"
                ? "Streaming focus events"
                : "python -m agent run"}
            </p>
          </div>
        </div>

        {/* Card 3: Applications */}
        <div className="bg-white border border-[#E2E8F0] rounded-xl p-4 shadow-2xs flex flex-col justify-between">
          <div className="flex items-center justify-between text-[#64748B]">
            <span className="text-[10px] font-bold uppercase tracking-wider text-[#64748B]">
              Applications
            </span>
            <svg className="w-3.5 h-3.5 text-[#94A3B8]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z" />
            </svg>
          </div>
          <div className="my-2.5">
            <div className="text-2xl font-bold font-mono text-[#0F172A] leading-tight">
              {loading ? (
                <span className="inline-block w-8 h-6 bg-slate-100 rounded animate-pulse" />
              ) : (
                connectedAppsCount
              )}
            </div>
            <p className="text-[11px] text-[#64748B] mt-0.5 truncate">
              {availableAppsCount} registered in registry
            </p>
          </div>
        </div>

        {/* Card 4: Workflows */}
        <div className="bg-white border border-[#E2E8F0] rounded-xl p-4 shadow-2xs flex flex-col justify-between">
          <div className="flex items-center justify-between text-[#64748B]">
            <span className="text-[10px] font-bold uppercase tracking-wider text-[#64748B]">
              Workflows
            </span>
            <svg className="w-3.5 h-3.5 text-[#94A3B8]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M7.217 10.907a2.25 2.25 0 100 2.186m0-2.186c.18.324.283.696.283 1.093s-.103.77-.283 1.093m0-2.186l9.566-5.314m-9.566 7.5l9.566 5.314m0 0a2.25 2.25 0 103.935 2.186 2.25 2.25 0 00-3.935-2.186zm0-12.814a2.25 2.25 0 103.933-2.185 2.25 2.25 0 00-3.933 2.185z" />
            </svg>
          </div>
          <div className="my-2.5">
            <div className="text-2xl font-bold font-mono text-[#0F172A] leading-tight">
              {loading ? (
                <span className="inline-block w-8 h-6 bg-slate-100 rounded animate-pulse" />
              ) : (
                discoveredCount
              )}
            </div>
            <p className="text-[11px] text-[#64748B] mt-0.5 truncate">
              {discoveredCount > 0 ? "Repetitions detected" : "Observing activity"}
            </p>
          </div>
        </div>

        {/* Card 5: Automations */}
        <div className="bg-white border border-[#E2E8F0] rounded-xl p-4 shadow-2xs flex flex-col justify-between">
          <div className="flex items-center justify-between text-[#64748B]">
            <span className="text-[10px] font-bold uppercase tracking-wider text-[#64748B]">
              Automations
            </span>
            <svg className="w-3.5 h-3.5 text-[#94A3B8]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
            </svg>
          </div>
          <div className="my-2.5">
            <div className="text-2xl font-bold font-mono text-[#0F172A] leading-tight">
              {historyLoading ? (
                <span className="inline-block w-8 h-6 bg-slate-100 rounded animate-pulse" />
              ) : (
                completedExecs
              )}
            </div>
            <p className="text-[11px] text-[#64748B] mt-0.5 truncate">
              {executions.length} total runs logged
            </p>
          </div>
        </div>

        {/* Card 6: Privacy & Safety */}
        <div className="bg-white border border-[#E2E8F0] rounded-xl p-4 shadow-2xs flex flex-col justify-between">
          <div className="flex items-center justify-between text-[#64748B]">
            <span className="text-[10px] font-bold uppercase tracking-wider text-[#64748B]">
              Privacy & Safety
            </span>
            <svg className="w-3.5 h-3.5 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
            </svg>
          </div>
          <div className="my-2.5">
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-500" />
              <span className="text-lg font-bold text-[#0F172A] leading-tight">
                Protected
              </span>
            </div>
            <p className="text-[11px] text-[#64748B] mt-0.5 truncate">
              Redaction & Human Gate
            </p>
          </div>
        </div>
      </div>

      {/* ==================================================
          4. WORKFLOW INTELLIGENCE SPOTLIGHT (Section 9)
          ================================================== */}
      <section className="bg-white border border-[#E2E8F0] rounded-xl p-5 shadow-2xs">
        <div className="flex items-center justify-between mb-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[11px] font-bold uppercase tracking-wider text-[#64748B]">
                Workflow Intelligence
              </span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200">
                Pattern Engine
              </span>
            </div>
            <p className="text-xs text-[#64748B] mt-0.5">
              Prominently recommended repetitive workflow detected across observed sessions
            </p>
          </div>

          <button
            onClick={() => onNavigate("workflows")}
            className="text-xs text-[#2563EB] hover:text-[#1D4ED8] font-semibold transition-colors duration-150 cursor-pointer"
          >
            All Workflows ({discoveredCount}) →
          </button>
        </div>

        {topWorkflow ? (
          <div className="rounded-xl border border-[#CBD5E1] bg-[#F8FAFC] p-5">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-[#E2E8F0]">
              <div>
                <div className="flex items-center gap-2.5 flex-wrap">
                  <h3 className="text-base font-bold text-[#0F172A]">
                    {topWorkflow.label || "Customer Request Processing"}
                  </h3>
                  <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200">
                    {topWorkflow.recommendation_status || "Recommended"}
                  </span>
                  <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 font-mono">
                    {Math.round((topWorkflow.confidence ?? 1.0) * 100)}% confidence
                  </span>
                </div>
                <p className="text-xs text-[#64748B] mt-1 font-mono">
                  {topWorkflow.occurrences} repetitions ·{" "}
                  {topWorkflow.session_ids?.length || 1} sessions
                </p>
              </div>

              <button
                onClick={() => onNavigate("workflows")}
                className="px-4 py-2 text-xs font-semibold rounded-lg bg-[#2563EB] hover:bg-[#1D4ED8] text-white shadow-2xs transition-colors duration-150 cursor-pointer shrink-0"
              >
                Review &amp; Automate
              </button>
            </div>

            {/* Step Sequence Flowchart */}
            <div className="mt-4">
              <span className="text-[10px] font-bold uppercase tracking-wider text-[#94A3B8] block mb-2.5">
                Synthesized Action Sequence ({topWorkflow.sequence?.length || 0} Steps)
              </span>
              <div className="flex items-center gap-2 overflow-x-auto pb-2">
                {topWorkflow.sequence && topWorkflow.sequence.length > 0 ? (
                  topWorkflow.sequence.map((step, idx) => (
                    <React.Fragment key={idx}>
                      <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-white border border-[#E2E8F0] shadow-2xs text-xs shrink-0">
                        <span className="w-4 h-4 rounded-full bg-slate-100 text-[#475569] text-[10px] font-mono font-bold flex items-center justify-center shrink-0">
                          {idx + 1}
                        </span>
                        <span className="font-medium text-[#0F172A] whitespace-nowrap">
                          {getActionDisplayLabel(step)}
                        </span>
                      </div>
                      {idx < (topWorkflow.sequence?.length ?? 0) - 1 && (
                        <span className="text-[#94A3B8] shrink-0 font-bold">
                          →
                        </span>
                      )}
                    </React.Fragment>
                  ))
                ) : (
                  <span className="text-xs text-[#94A3B8]">
                    No sequence steps available
                  </span>
                )}
              </div>
            </div>
          </div>
        ) : (
          <div className="text-center py-10 px-4 border border-dashed border-[#E2E8F0] rounded-xl bg-[#F8FAFC]">
            <div className="w-10 h-10 rounded-full bg-slate-100 border border-slate-200 flex items-center justify-center text-slate-400 mx-auto mb-3">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
              </svg>
            </div>
            <h4 className="text-sm font-semibold text-[#0F172A]">
              No repeated workflows discovered yet.
            </h4>
            <p className="text-xs text-[#64748B] mt-1 max-w-md mx-auto">
              Keep working normally and WorkFlowOS will look for recurring patterns across your desktop and connected applications.
            </p>
            <button
              onClick={() => onNavigate("activity")}
              className="mt-4 px-3.5 py-1.5 text-xs font-semibold rounded-lg bg-white border border-[#E2E8F0] hover:bg-[#F8FAFC] text-[#0F172A] shadow-2xs transition-colors duration-150 cursor-pointer"
            >
              View Activity Stream
            </button>
          </div>
        )}
      </section>

      {/* ==================================================
          5. MAIN TWO-COLUMN SECTION: LIVE ACTIVITY & AUTOMATIONS
          ================================================== */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Activity (Section 10) */}
        <section className="bg-white border border-[#E2E8F0] rounded-xl p-5 shadow-2xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-3.5">
              <div>
                <h3 className="text-xs font-bold uppercase tracking-wider text-[#64748B]">
                  Recent Activity
                </h3>
                <p className="text-[11px] text-[#64748B] mt-0.5">
                  Latest observed actions captured from desktop and demo applications
                </p>
              </div>
              <button
                onClick={() => onNavigate("activity")}
                className="text-[11px] text-[#2563EB] hover:text-[#1D4ED8] font-semibold transition-colors duration-150 cursor-pointer"
              >
                View All ({events.length}) →
              </button>
            </div>

            {loading ? (
              <div className="space-y-2 py-4">
                {[1, 2, 3, 4].map((i) => (
                  <div key={i} className="h-10 bg-slate-50 border border-slate-100 rounded-lg animate-pulse" />
                ))}
              </div>
            ) : recentEvents.length === 0 ? (
              <div className="py-10 text-center text-xs text-[#94A3B8] border border-dashed border-[#E2E8F0] rounded-xl bg-[#F8FAFC]">
                <p className="font-semibold text-[#0F172A]">Nothing automated yet</p>
                <p className="text-[11px] text-[#64748B] mt-1 max-w-sm mx-auto">
                  WorkFlowOS is observing your activity and will surface repeated workflows here. Start `python -m agent run` or trigger actions in Demo Applications.
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-[#F8FAFC] text-[#64748B] border-b border-[#E2E8F0]">
                    <tr>
                      <th className="py-2.5 px-3 whitespace-nowrap">Application</th>
                      <th className="py-2.5 px-3 whitespace-nowrap">Action</th>
                      <th className="py-2.5 px-3 whitespace-nowrap">Target</th>
                      <th className="py-2.5 px-3 whitespace-nowrap text-right">Time</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#E2E8F0]">
                    {recentEvents.map((ev) => {
                      const t = formatTimestamp(ev.timestamp);
                      const badgeClass = getAppBadgeClass(ev.application);
                      const dotColor = getAppDotColor(ev.application);
                      return (
                        <tr key={ev.id} className="hover:bg-[#F8FAFC] transition-colors duration-100">
                          <td className="py-2.5 px-3 whitespace-nowrap">
                            <span className="inline-flex items-center gap-1.5">
                              <span className={`w-1.5 h-1.5 rounded-full ${dotColor}`} />
                              <span
                                className={`text-[10px] font-medium px-2 py-0.5 rounded border ${badgeClass}`}
                              >
                                {getApplicationDisplayName(ev.application)}
                              </span>
                            </span>
                          </td>
                          <td className="py-2.5 px-3 font-mono font-medium text-[#0F172A] whitespace-nowrap">
                            {formatEventStep(ev.event_type)}
                          </td>
                          <td className="py-2.5 px-3 text-[#64748B] max-w-36 truncate font-mono text-[11px]">
                            {ev.target || "—"}
                          </td>
                          <td className="py-2.5 px-3 font-mono text-[#64748B] whitespace-nowrap text-right">
                            {t.relative || t.full}
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

        {/* Recent Automations (Section 11) */}
        <section className="bg-white border border-[#E2E8F0] rounded-xl p-5 shadow-2xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-3.5">
              <div>
                <h3 className="text-xs font-bold uppercase tracking-wider text-[#64748B]">
                  Recent Automations
                </h3>
                <p className="text-[11px] text-[#64748B] mt-0.5">
                  Automated workflow runs, outcomes, and intervention logs
                </p>
              </div>
              <button
                onClick={() => onNavigate("executions")}
                className="text-[11px] text-[#2563EB] hover:text-[#1D4ED8] font-semibold transition-colors duration-150 cursor-pointer"
              >
                View History ({executions.length}) →
              </button>
            </div>

            {historyLoading ? (
              <div className="space-y-2 py-4">
                {[1, 2, 3, 4].map((i) => (
                  <div key={i} className="h-10 bg-slate-50 border border-slate-100 rounded-lg animate-pulse" />
                ))}
              </div>
            ) : recentExecutions.length === 0 ? (
              <div className="py-10 text-center text-xs text-[#94A3B8] border border-dashed border-[#E2E8F0] rounded-xl bg-[#F8FAFC]">
                <p className="font-semibold text-[#0F172A]">No executions yet</p>
                <p className="text-[11px] text-[#64748B] mt-1 max-w-sm mx-auto">
                  Approved workflow runs will appear here. Approve and execute a workflow to start recording automated execution history.
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-[#F8FAFC] text-[#64748B] border-b border-[#E2E8F0]">
                    <tr>
                      <th className="py-2.5 px-3 whitespace-nowrap">Status</th>
                      <th className="py-2.5 px-3 whitespace-nowrap">Workflow</th>
                      <th className="py-2.5 px-3 whitespace-nowrap">Steps</th>
                      <th className="py-2.5 px-3 whitespace-nowrap">Duration</th>
                      <th className="py-2.5 px-3 whitespace-nowrap">Time</th>
                      <th className="py-2.5 px-3 whitespace-nowrap text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#E2E8F0]">
                    {recentExecutions.map((rec) => {
                      const st = getExecutionStatusBadge(rec.status);
                      const t = rec.completed_at
                        ? formatTimestamp(rec.completed_at)
                        : rec.started_at
                        ? formatTimestamp(rec.started_at)
                        : null;
                      const duration = getExecutionDuration(rec);

                      return (
                        <tr key={rec.execution_id} className="hover:bg-[#F8FAFC] transition-colors duration-100">
                          <td className="py-2.5 px-3 whitespace-nowrap">
                            <span
                              className={`inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full border ${st.badgeClass}`}
                            >
                              <span>{st.symbol}</span>
                              <span>{st.label}</span>
                            </span>
                          </td>
                          <td className="py-2.5 px-3 font-medium text-[#0F172A] max-w-40 truncate">
                            {rec.workflow_name || "Automation Workflow"}
                          </td>
                          <td className="py-2.5 px-3 whitespace-nowrap font-mono text-[#64748B]">
                            {rec.completed_actions?.length ?? 0}/{rec.total_actions ?? 0}
                          </td>
                          <td className="py-2.5 px-3 whitespace-nowrap font-mono text-[#64748B]">
                            {duration}
                          </td>
                          <td className="py-2.5 px-3 font-mono text-[#94A3B8] whitespace-nowrap">
                            {t ? t.relative || t.full : "—"}
                          </td>
                          <td className="py-2.5 px-3 text-right whitespace-nowrap">
                            <button
                              onClick={() => setSelectedExecution(rec)}
                              className="px-2.5 py-1 text-[11px] font-medium rounded-md bg-white hover:bg-[#F1F5F9] border border-[#CBD5E1] text-[#0F172A] transition-colors duration-150 cursor-pointer shadow-2xs"
                            >
                              Inspect
                            </button>
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

      {/* ==================================================
          6. BOUNDED EXECUTION INSPECTION MODAL (Section 1)
          ================================================== */}
      {selectedExecution && (
        <ExecutionDetailModal
          execution={selectedExecution}
          onClose={() => setSelectedExecution(null)}
        />
      )}
    </div>
  );
}
