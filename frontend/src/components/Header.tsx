"use client";

import React from "react";
import { ViewId } from "@/lib/types";
import ThemeToggle from "@/components/ThemeToggle";

const VIEW_LABELS: Record<ViewId, string> = {
  dashboard: "Overview",
  activity: "Activity",
  workflows: "Workflows",
  discovery: "Workflow Discovery",
  builder: "Workflow Builder",
  executions: "Executions",
  applications: "Applications",
  settings: "Settings & Privacy",
};

const VIEW_DESCRIPTIONS: Record<ViewId, string> = {
  dashboard: "System overview, agent connectivity, and live telemetry",
  activity: "Live event stream captured from desktop agents and demo applications",
  workflows: "Complete workflow lifecycle: discovery, understanding, learning, and automation",
  discovery: "Algorithmic detection of repeated multi-step workflow patterns",
  builder: "Declarative workflow engine editor, branching conditions, and retry policies",
  executions: "Automated execution log, step results, and human-in-the-loop control",
  applications: "Ecosystem applications, read-only vs mutating capabilities, and safety controls",
  settings: "Privacy controls, data retention governance, and system configuration",
};

interface HeaderProps {
  activeView: ViewId;
  backendStatus: "connected" | "disconnected" | "checking";
  lastRefreshed: Date | null;
  refreshing: boolean;
  onRefresh: () => void;
  onNavigate?: (view: ViewId) => void;
}

export default function Header({
  activeView,
  backendStatus,
  lastRefreshed,
  refreshing,
  onRefresh,
  onNavigate,
}: HeaderProps) {
  return (
    <header className="h-16 bg-white dark:bg-[#111827] border-b border-[#E2E8F0] dark:border-[#1E293B] flex items-center justify-between px-6 shrink-0 sticky top-0 z-20 shadow-2xs transition-colors duration-150">
      {/* Breadcrumb & Title */}
      <div className="flex items-center gap-2.5 min-w-0">
        <button
          type="button"
          onClick={() => onNavigate?.("dashboard")}
          className="text-xs font-semibold text-[#64748B] dark:text-[#94A3B8] hover:text-[#2563EB] dark:hover:text-[#3B82F6] transition-colors duration-150 hidden sm:inline cursor-pointer focus:outline-hidden"
          title="Return to WorkFlowOS Overview"
        >
          WorkFlowOS
        </button>
        <svg
          className="w-3.5 h-3.5 text-[#CBD5E1] dark:text-[#334155] hidden sm:inline shrink-0"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
        </svg>
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h1 className="text-sm font-semibold text-[#0F172A] dark:text-[#F8FAFC] truncate">
              {VIEW_LABELS[activeView]}
            </h1>
            <span className="hidden md:inline text-xs text-[#64748B] dark:text-[#94A3B8] truncate">
              — {VIEW_DESCRIPTIONS[activeView]}
            </span>
          </div>
        </div>
      </div>

      {/* Right Controls */}
      <div className="flex items-center gap-2.5 sm:gap-3 shrink-0">
        {/* Last Refreshed */}
        {lastRefreshed && (
          <span className="hidden lg:flex items-center gap-1.5 text-[11px] text-[#64748B] dark:text-[#94A3B8] font-mono">
            <span className="w-1.5 h-1.5 rounded-full bg-[#94A3B8] dark:bg-[#64748B]" />
            Updated{" "}
            {lastRefreshed.toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
              second: "2-digit",
            })}
          </span>
        )}

        {/* Status Pill */}
        <div
          className={`flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full border transition-all ${
            backendStatus === "connected"
              ? "bg-emerald-50 dark:bg-emerald-950/40 border-emerald-200 dark:border-emerald-800/60 text-emerald-700 dark:text-emerald-400"
              : backendStatus === "checking"
              ? "bg-amber-50 dark:bg-amber-950/40 border-amber-200 dark:border-amber-800/60 text-amber-700 dark:text-amber-400"
              : "bg-rose-50 dark:bg-rose-950/40 border-rose-200 dark:border-rose-800/60 text-rose-700 dark:text-rose-400"
          }`}
        >
          <span
            className={`w-1.5 h-1.5 rounded-full ${
              backendStatus === "connected"
                ? "bg-[#16A34A] dark:bg-[#22C55E] animate-pulse"
                : backendStatus === "checking"
                ? "bg-[#F59E0B] dark:bg-[#FBBF24]"
                : "bg-[#DC2626] dark:bg-[#EF4444]"
            }`}
          />
          <span className="capitalize">{backendStatus}</span>
        </div>

        {/* Theme Toggle Button */}
        <ThemeToggle />

        {/* Refresh Button */}
        <button
          onClick={onRefresh}
          disabled={refreshing}
          className="flex items-center gap-2 px-3 py-1.5 text-xs font-medium rounded-lg bg-white dark:bg-[#162035] hover:bg-[#F8FAFC] dark:hover:bg-[#1E293B] hover:shadow-xs border border-[#E2E8F0] dark:border-[#1E293B] text-[#0F172A] dark:text-[#F8FAFC] shadow-2xs transition-all duration-150 active:translate-y-px disabled:opacity-60 cursor-pointer"
          title="Refresh real data"
        >
          <svg
            className={`w-3.5 h-3.5 ${
              refreshing ? "animate-spin text-[#2563EB] dark:text-[#3B82F6]" : "text-[#475569] dark:text-[#94A3B8]"
            }`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
            />
          </svg>
          <span className="hidden sm:inline">
            {refreshing ? "Refreshing…" : "Refresh"}
          </span>
        </button>
      </div>
    </header>
  );
}
