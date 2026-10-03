"use client";

import React from "react";
import { ActivityEvent, AutomationExecutionRecord, DiscoveryResult } from "@/lib/types";
import { formatEventStep, statusBadgeConfig, getApplicationDisplayName } from "@/lib/utils";

interface DashboardViewProps {
  events: ActivityEvent[];
  executions: AutomationExecutionRecord[];
  discovery: DiscoveryResult | null;
  loading: boolean;
  historyLoading: boolean;
  onNavigate: (view: "activity" | "discovery" | "executions") => void;
}

function MetricCard({
  label, value, sub, accent, icon, loading,
}: {
  label: string;
  value: string | number;
  sub?: string;
  accent: string;
  icon: React.ReactNode;
  loading?: boolean;
}) {
  return (
    <div className="bg-zinc-900/60 border border-zinc-800/80 rounded-xl p-5 relative overflow-hidden group hover:border-zinc-700 transition">
      <div className={`absolute top-0 right-0 w-24 h-24 ${accent} rounded-full blur-2xl opacity-60 pointer-events-none`} />
      <div className="flex items-center justify-between text-zinc-400 mb-2">
        <span className="text-xs font-semibold uppercase tracking-wider">{label}</span>
        <span className="text-zinc-500">{icon}</span>
      </div>
      <div className="text-3xl font-bold font-mono text-white">
        {loading ? <div className="h-8 w-14 bg-zinc-800 rounded animate-pulse" /> : value}
      </div>
      {sub && <p className="text-[11px] text-zinc-500 mt-1 truncate">{sub}</p>}
    </div>
  );
}

export default function DashboardView({
  events, executions, discovery, loading, historyLoading, onNavigate,
}: DashboardViewProps) {
  const completed = executions.filter((e) => e.status === "completed").length;
  const failed = executions.filter((e) => e.status === "failed" || e.status === "paused").length;
  const uniqueApps = new Set(events.map((e) => e.application)).size;
  const successRate = executions.length > 0
    ? Math.round((completed / executions.length) * 100)
    : null;

  const recentEvents = events.slice(0, 8);
  const recentExecutions = executions.slice(0, 5);

  return (
    <div className="space-y-6 p-6">
      {/* KPI Row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          label="Events Captured"
          value={events.length}
          sub="From /api/events · MongoDB"
          accent="bg-cyan-500/5"
          loading={loading}
          icon={
            <svg className="w-5 h-5 text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          }
        />
        <MetricCard
          label="Active Apps"
          value={uniqueApps}
          sub={loading ? "" : `${new Set(events.map((e) => e.event_type)).size} event types`}
          accent="bg-purple-500/5"
          loading={loading}
          icon={
            <svg className="w-5 h-5 text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
            </svg>
          }
        />
        <MetricCard
          label="Workflows Found"
          value={discovery?.workflows.length ?? 0}
          sub={discovery?.detected ? "Patterns detected across sessions" : "No patterns yet"}
          accent="bg-indigo-500/5"
          loading={false}
          icon={
            <svg className="w-5 h-5 text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2m0 10V7m0 10a2 2 0 002 2h2a2 2 0 002-2V7a2 2 0 00-2-2h-2a2 2 0 00-2 2" />
            </svg>
          }
        />
        <MetricCard
          label="Success Rate"
          value={successRate !== null ? `${successRate}%` : "—"}
          sub={executions.length > 0 ? `${completed} of ${executions.length} executions` : "No executions yet"}
          accent="bg-emerald-500/5"
          loading={historyLoading}
          icon={
            <svg className="w-5 h-5 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          }
        />
      </div>

      {/* Two column layout */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Recent Activity Feed */}
        <section className="bg-zinc-900/50 border border-zinc-800/80 rounded-xl overflow-hidden">
          <div className="px-5 py-3.5 border-b border-zinc-800/60 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-white flex items-center gap-2">
              <svg className="w-4 h-4 text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
              Recent Activity
            </h2>
            <button
              onClick={() => onNavigate("activity")}
              className="text-xs text-indigo-400 hover:text-indigo-300 transition"
            >
              View all →
            </button>
          </div>
          <div className="divide-y divide-zinc-800/50">
            {loading ? (
              <div className="p-5 space-y-3">
                {[...Array(4)].map((_, i) => (
                  <div key={i} className="flex gap-3 animate-pulse">
                    <div className="h-4 w-20 bg-zinc-800 rounded" />
                    <div className="h-4 w-24 bg-zinc-800 rounded" />
                    <div className="h-4 flex-1 bg-zinc-800 rounded" />
                  </div>
                ))}
              </div>
            ) : recentEvents.length === 0 ? (
              <div className="py-10 text-center">
                <p className="text-sm text-zinc-500">No events captured yet.</p>
                <p className="text-xs text-zinc-600 mt-1">Run the desktop agent or seed test data.</p>
              </div>
            ) : (
              recentEvents.map((ev) => (
                <div key={ev.id} className="px-5 py-3 hover:bg-zinc-800/30 transition flex items-center gap-3">
                  <div className="shrink-0 w-1.5 h-1.5 rounded-full bg-cyan-500" />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 text-xs">
                      <span className="font-mono text-cyan-300 font-medium">{formatEventStep(ev.event_type)}</span>
                      <span className="text-zinc-600">·</span>
                      <span className="text-zinc-400 truncate">{ev.application}</span>
                    </div>
                    {ev.target && (
                      <p className="text-[11px] text-zinc-600 truncate mt-0.5">{ev.target}</p>
                    )}
                  </div>
                  <span className="text-[10px] text-zinc-600 font-mono shrink-0">
                    {new Date(ev.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                  </span>
                </div>
              ))
            )}
          </div>
        </section>

        {/* Recent Executions */}
        <section className="bg-zinc-900/50 border border-zinc-800/80 rounded-xl overflow-hidden">
          <div className="px-5 py-3.5 border-b border-zinc-800/60 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-white flex items-center gap-2">
              <svg className="w-4 h-4 text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
              </svg>
              Recent Executions
              {executions.length > 0 && (
                <span className="text-[10px] font-mono px-1.5 py-0.5 bg-indigo-950/60 border border-indigo-800/50 text-indigo-400 rounded-full">
                  {completed}/{executions.length}
                </span>
              )}
            </h2>
            <button
              onClick={() => onNavigate("executions")}
              className="text-xs text-indigo-400 hover:text-indigo-300 transition"
            >
              View all →
            </button>
          </div>
          <div className="divide-y divide-zinc-800/50">
            {historyLoading ? (
              <div className="p-5 space-y-3">
                {[...Array(3)].map((_, i) => (
                  <div key={i} className="flex gap-3 animate-pulse">
                    <div className="h-5 w-5 bg-zinc-800 rounded-full" />
                    <div className="flex-1 space-y-1.5">
                      <div className="h-4 w-40 bg-zinc-800 rounded" />
                      <div className="h-3 w-24 bg-zinc-800 rounded" />
                    </div>
                    <div className="h-5 w-16 bg-zinc-800 rounded-full" />
                  </div>
                ))}
              </div>
            ) : recentExecutions.length === 0 ? (
              <div className="py-10 text-center">
                <p className="text-sm text-zinc-500">No executions yet.</p>
                <p className="text-xs text-zinc-600 mt-1">Approve a workflow to run automation.</p>
              </div>
            ) : (
              recentExecutions.map((ex) => {
                const cfg = statusBadgeConfig(ex.status);
                return (
                  <div key={ex.execution_id} className="px-5 py-3 hover:bg-zinc-800/30 transition">
                    <div className="flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-white truncate">
                          {ex.workflow_name || "Automation Workflow"}
                        </p>
                        <p className="text-[11px] text-zinc-500 mt-0.5">
                          {ex.completed_actions.length}/{ex.total_actions} steps
                          {ex.execution_time_seconds != null && ` · ${ex.execution_time_seconds}s`}
                          {ex.applications && ex.applications.length > 0 && ` · ${ex.applications.map(getApplicationDisplayName).join(", ")}`}
                        </p>
                      </div>
                      <span className={`shrink-0 text-[10px] font-semibold px-2 py-0.5 rounded-full border ${cfg.className}`}>
                        {cfg.label}
                      </span>
                    </div>
                    {/* Progress bar */}
                    <div className="mt-2 h-1 bg-zinc-800 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all ${
                          ex.status === "completed" ? "bg-emerald-500"
                          : ex.status === "failed" ? "bg-rose-500"
                          : ex.status === "paused" ? "bg-amber-500"
                          : "bg-indigo-500"
                        }`}
                        style={{ width: `${ex.total_actions > 0 ? (ex.completed_actions.length / ex.total_actions) * 100 : 0}%` }}
                      />
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </section>
      </div>

      {/* Discovery Summary Banner */}
      {discovery?.detected && discovery.workflows.length > 0 && (
        <section className="bg-indigo-950/30 border border-indigo-700/40 rounded-xl px-5 py-4 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-indigo-900/60 border border-indigo-700/50 flex items-center justify-center shrink-0">
              <svg className="w-4 h-4 text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
              </svg>
            </div>
            <div>
              <p className="text-sm font-semibold text-indigo-200">
                {discovery.workflows.length} workflow pattern{discovery.workflows.length > 1 ? "s" : ""} discovered
              </p>
              <p className="text-xs text-indigo-400/70 mt-0.5">
                AI can analyse these patterns and propose automation
              </p>
            </div>
          </div>
          <button
            onClick={() => onNavigate("discovery")}
            className="shrink-0 px-4 py-2 text-xs font-semibold rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white transition active:scale-95 cursor-pointer"
          >
            Review Patterns
          </button>
        </section>
      )}

      {/* System health / stats row */}
      <section className="grid grid-cols-3 gap-4 text-center">
        <div className="bg-zinc-900/40 border border-zinc-800/60 rounded-xl py-4">
          <div className="text-xl font-bold font-mono text-white">{failed}</div>
          <div className="text-[11px] text-zinc-500 mt-1">Failed / Paused</div>
        </div>
        <div className="bg-zinc-900/40 border border-zinc-800/60 rounded-xl py-4">
          <div className="text-xl font-bold font-mono text-white">
            {executions.reduce((s, e) => s + (e.execution_time_seconds ?? 0), 0).toFixed(1)}s
          </div>
          <div className="text-[11px] text-zinc-500 mt-1">Total Exec Time</div>
        </div>
        <div className="bg-zinc-900/40 border border-zinc-800/60 rounded-xl py-4">
          <div className="text-xl font-bold font-mono text-white">
            {executions.reduce((s, e) => s + e.completed_actions.length, 0)}
          </div>
          <div className="text-[11px] text-zinc-500 mt-1">Actions Completed</div>
        </div>
      </section>
    </div>
  );
}
