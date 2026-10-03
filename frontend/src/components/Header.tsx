"use client";

import React from "react";
import { ViewId } from "@/lib/types";

const VIEW_LABELS: Record<ViewId, string> = {
  dashboard: "Dashboard",
  activity: "Activity Feed",
  discovery: "Workflow Discovery",
  builder: "Workflow Builder",
  executions: "Execution History",
  settings: "Settings",
};

const VIEW_DESCRIPTIONS: Record<ViewId, string> = {
  dashboard: "System overview and recent activity summary",
  activity: "Live event stream from the desktop agent",
  discovery: "Detected repeated workflow patterns",
  builder: "Declarative workflow editor and launcher",
  executions: "Automation run history, status and logs",
  settings: "Agent configuration and system preferences",
};

interface HeaderProps {
  activeView: ViewId;
  backendStatus: "connected" | "disconnected" | "checking";
  lastRefreshed: Date | null;
  refreshing: boolean;
  onRefresh: () => void;
}

export default function Header({ activeView, backendStatus, lastRefreshed, refreshing, onRefresh }: HeaderProps) {
  return (
    <header className="h-14 bg-zinc-900/80 border-b border-zinc-800/60 flex items-center justify-between px-6 shrink-0 backdrop-blur-sm sticky top-0 z-20">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm">
        <span className="text-zinc-500 text-xs">WorkFlowOS</span>
        <svg className="w-3 h-3 text-zinc-700" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
        </svg>
        <span className="font-semibold text-zinc-100">{VIEW_LABELS[activeView]}</span>
        <span className="hidden sm:block text-[11px] text-zinc-500 ml-2">— {VIEW_DESCRIPTIONS[activeView]}</span>
      </div>

      {/* Right controls */}
      <div className="flex items-center gap-3">
        {/* Last refreshed */}
        {lastRefreshed && (
          <span className="hidden md:block text-[11px] text-zinc-600 font-mono">
            Updated {lastRefreshed.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
          </span>
        )}

        {/* Status indicator */}
        <div className={`hidden sm:flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full border
          ${backendStatus === "connected"
            ? "bg-emerald-950/40 border-emerald-800/50 text-emerald-400"
            : backendStatus === "checking"
            ? "bg-amber-950/40 border-amber-800/50 text-amber-400"
            : "bg-rose-950/40 border-rose-800/50 text-rose-400"
          }`}>
          <span className={`w-1.5 h-1.5 rounded-full ${
            backendStatus === "connected" ? "bg-emerald-400 animate-pulse"
            : backendStatus === "checking" ? "bg-amber-400"
            : "bg-rose-400"
          }`} />
          <span className="capitalize">{backendStatus}</span>
        </div>

        {/* Refresh button */}
        <button
          onClick={onRefresh}
          disabled={refreshing}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 text-zinc-200 transition active:scale-95 disabled:opacity-60 cursor-pointer"
          title="Refresh all data"
        >
          <svg
            className={`w-3.5 h-3.5 ${refreshing ? "animate-spin text-cyan-400" : "text-zinc-400"}`}
            fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          <span>{refreshing ? "Refreshing…" : "Refresh"}</span>
        </button>
      </div>
    </header>
  );
}
