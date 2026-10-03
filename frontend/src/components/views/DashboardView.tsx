"use client";

import React from "react";
import { ActivityEvent, AutomationExecutionRecord, DiscoveryResult } from "@/lib/types";
import { formatEventStep, statusBadgeConfig, getApplicationDisplayName, getAppBadgeClass, formatTimestamp } from "@/lib/utils";

interface DashboardViewProps {
  events: ActivityEvent[];
  executions: AutomationExecutionRecord[];
  discovery: DiscoveryResult | null;
  loading: boolean;
  historyLoading: boolean;
  onNavigate: (view: "activity" | "discovery" | "executions" | "builder") => void;
}

function MetricCard({
  label,
  value,
  sub,
  icon,
  iconBg,
  iconColor,
  loading,
}: {
  label: string;
  value: string | number;
  sub?: string;
  icon: React.ReactNode;
  iconBg: string;
  iconColor: string;
  loading?: boolean;
}) {
  return (
    <div className="bg-white border border-[#E2E8F0] rounded-xl p-5 shadow-2xs hover:shadow-xs transition flex flex-col justify-between group">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-semibold uppercase tracking-wider text-[#64748B]">
          {label}
        </span>
        <div className={`w-8 h-8 rounded-lg ${iconBg} ${iconColor} flex items-center justify-center shrink-0`}>
          {icon}
        </div>
      </div>
      <div>
        <div className="text-2xl sm:text-3xl font-bold font-mono text-[#0F172A] tracking-tight">
          {loading ? (
            <div className="h-8 w-16 bg-[#F1F5F9] rounded animate-pulse" />
          ) : (
            value
          )}
        </div>
        {sub && (
          <p className="text-[11px] text-[#64748B] mt-1.5 truncate">
            {sub}
          </p>
        )}
      </div>
    </div>
  );
}

export default function DashboardView({
  events,
  executions,
  discovery,
  loading,
  historyLoading,
  onNavigate,
}: DashboardViewProps) {
  const completed = executions.filter((e) => e.status === "completed").length;
  const failed = executions.filter((e) => e.status === "failed" || e.status === "paused").length;
  const uniqueApps = Array.from(new Set(events.map((e) => e.application)));
  const successRate =
    executions.length > 0
      ? Math.round((completed / executions.length) * 100)
      : null;

  const recentEvents = events.slice(0, 7);
  const recentExecutions = executions.slice(0, 5);

  // Derive real application distribution from events
  const appCounts: Record<string, number> = {};
  events.forEach((ev) => {
    appCounts[ev.application] = (appCounts[ev.application] || 0) + 1;
  });
  const topApps = Object.entries(appCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 4);

  return (
    <div className="space-y-6 p-6 max-w-7xl mx-auto">
      {/* Workspace Header & Quick Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white border border-[#E2E8F0] rounded-xl p-5 shadow-2xs">
        <div>
          <h2 className="text-lg font-bold text-[#0F172A] tracking-tight">
            Workspace Overview
          </h2>
          <p className="text-xs text-[#64748B] mt-0.5">
            Observational desktop telemetry, discovered patterns, and autonomous workflow executions.
          </p>
        </div>
        <div className="flex items-center gap-2.5 shrink-0">
          <button
            onClick={() => onNavigate("discovery")}
            className="px-3.5 py-2 text-xs font-semibold rounded-lg bg-white border border-[#E2E8F0] hover:bg-[#F8FAFC] text-[#0F172A] shadow-2xs transition active:scale-97 cursor-pointer"
          >
            Review Discovered ({discovery?.workflows.length ?? 0})
          </button>
          <button
            onClick={() => onNavigate("builder")}
            className="flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold rounded-lg bg-[#2563EB] hover:bg-[#1D4ED8] text-white shadow-2xs transition active:scale-97 cursor-pointer"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
            </svg>
            <span>Create Workflow</span>
          </button>
        </div>
      </div>

      {/* KPI Cards Row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          label="Events Captured"
          value={events.length}
          sub="Live ingested events"
          iconBg="bg-blue-50"
          iconColor="text-[#2563EB]"
          loading={loading}
          icon={
            <svg className="w-4.5 h-4.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          }
        />
        <MetricCard
          label="Active Applications"
          value={uniqueApps.length}
          sub={loading ? "" : `${new Set(events.map((e) => e.event_type)).size} event types active`}
          iconBg="bg-purple-50"
          iconColor="text-purple-600"
          loading={loading}
          icon={
            <svg className="w-4.5 h-4.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
            </svg>
          }
        />
        <MetricCard
          label="Workflows Found"
          value={discovery?.workflows.length ?? 0}
          sub={discovery?.detected ? "Repeated sequences detected" : "Scanning for patterns"}
          iconBg="bg-emerald-50"
          iconColor="text-[#16A34A]"
          loading={false}
          icon={
            <svg className="w-4.5 h-4.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
          }
        />
        <MetricCard
          label="Success Rate"
          value={successRate !== null ? `${successRate}%` : "—"}
          sub={executions.length > 0 ? `${completed} of ${executions.length} automated runs` : "No executions logged"}
          iconBg="bg-sky-50"
          iconColor="text-sky-600"
          loading={historyLoading}
          icon={
            <svg className="w-4.5 h-4.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          }
        />
      </div>

      {/* Discovery Insight Banner if patterns exist */}
      {discovery?.detected && discovery.workflows.length > 0 && (
        <section className="bg-white border border-[#BFDBFE] rounded-xl p-4.5 flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-2xs relative overflow-hidden">
          <div className="flex items-center gap-3.5">
            <div className="w-9 h-9 rounded-lg bg-[#EFF6FF] border border-[#BFDBFE] flex items-center justify-center shrink-0 text-[#2563EB]">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold text-[#0F172A]">
                  {discovery.workflows.length} Automated Workflow Pattern{discovery.workflows.length > 1 ? "s" : ""} Discovered
                </span>
                <span className="text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200">
                  Ready to Automate
                </span>
              </div>
              <p className="text-xs text-[#64748B] mt-0.5">
                Observed {discovery.workflows[0]?.occurrences || 3} repeated sessions in &quot;{discovery.workflows[0]?.label || "Pattern"}&quot;. AI can validate and generate proposal.
              </p>
            </div>
          </div>
          <button
            onClick={() => onNavigate("discovery")}
            className="shrink-0 px-4 py-2 text-xs font-semibold rounded-lg bg-[#2563EB] hover:bg-[#1D4ED8] text-white shadow-2xs transition active:scale-97 cursor-pointer"
          >
            Review & Automate
          </button>
        </section>
      )}

      {/* Application Telemetry Distribution */}
      {topApps.length > 0 && (
        <section className="bg-white border border-[#E2E8F0] rounded-xl p-5 shadow-2xs">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-[#64748B]">
              Application Activity Distribution
            </h3>
            <span className="text-xs text-[#64748B]">
              {events.length} total events
            </span>
          </div>
          {/* Proportion bar */}
          <div className="h-2 w-full bg-[#F1F5F9] rounded-full overflow-hidden flex">
            {topApps.map(([app, count], idx) => {
              const pct = (count / events.length) * 100;
              const colors = ["bg-[#2563EB]", "bg-purple-500", "bg-emerald-500", "bg-amber-500"];
              return (
                <div
                  key={app}
                  style={{ width: `${pct}%` }}
                  className={`h-full ${colors[idx % colors.length]}`}
                  title={`${app}: ${count} (${pct.toFixed(0)}%)`}
                />
              );
            })}
          </div>
          {/* Legend */}
          <div className="flex flex-wrap items-center gap-4 mt-3">
            {topApps.map(([app, count], idx) => {
              const colors = ["bg-[#2563EB]", "bg-purple-500", "bg-emerald-500", "bg-amber-500"];
              const pct = ((count / events.length) * 100).toFixed(0);
              return (
                <div key={app} className="flex items-center gap-1.5 text-xs text-[#475569]">
                  <span className={`w-2 h-2 rounded-full ${colors[idx % colors.length]}`} />
                  <span className="font-medium text-[#0F172A]">{getApplicationDisplayName(app)}</span>
                  <span className="text-[#94A3B8]">({count} · {pct}%)</span>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* Two Column Grid: Activity Feed & Executions */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Activity Section */}
        <section className="bg-white border border-[#E2E8F0] rounded-xl overflow-hidden shadow-2xs flex flex-col">
          <div className="px-5 py-3.5 border-b border-[#E2E8F0] bg-[#F8FAFC] flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-[#2563EB]" />
              <h3 className="text-xs font-semibold uppercase tracking-wider text-[#0F172A]">
                Recent Desktop Activity
              </h3>
            </div>
            <button
              onClick={() => onNavigate("activity")}
              className="text-xs font-medium text-[#2563EB] hover:text-[#1D4ED8] transition cursor-pointer"
            >
              View all →
            </button>
          </div>

          <div className="divide-y divide-[#E2E8F0] overflow-y-auto flex-1">
            {loading ? (
              <div className="p-5 space-y-3">
                {[...Array(4)].map((_, i) => (
                  <div key={i} className="flex items-center gap-3 animate-pulse">
                    <div className="h-4 w-20 bg-[#F1F5F9] rounded" />
                    <div className="h-4 w-28 bg-[#F1F5F9] rounded" />
                    <div className="h-4 flex-1 bg-[#F1F5F9] rounded" />
                  </div>
                ))}
              </div>
            ) : recentEvents.length === 0 ? (
              <div className="py-12 text-center px-4">
                <div className="w-10 h-10 rounded-full bg-[#F1F5F9] text-[#94A3B8] flex items-center justify-center mx-auto mb-2">
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                </div>
                <p className="text-xs font-medium text-[#0F172A]">No activity events captured yet</p>
                <p className="text-[11px] text-[#64748B] mt-1">Run `python -m agent run` or seed demo events.</p>
              </div>
            ) : (
              recentEvents.map((ev) => {
                const ts = formatTimestamp(ev.timestamp);
                const badgeClass = getAppBadgeClass(ev.application);
                return (
                  <div
                    key={ev.id}
                    className="px-5 py-3 hover:bg-[#F8FAFC] transition flex items-center justify-between gap-3 text-xs"
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <span className={`text-[10px] font-medium px-2 py-0.5 rounded border shrink-0 ${badgeClass}`}>
                        {getApplicationDisplayName(ev.application)}
                      </span>
                      <span className="font-mono text-[#0F172A] font-semibold truncate">
                        {formatEventStep(ev.event_type)}
                      </span>
                      {ev.target && (
                        <span className="text-[#64748B] truncate hidden sm:inline">
                          · {ev.target}
                        </span>
                      )}
                    </div>
                    <span className="text-[11px] text-[#94A3B8] font-mono shrink-0">
                      {ts.relative || ts.full}
                    </span>
                  </div>
                );
              })
            )}
          </div>
        </section>

        {/* Recent Executions Section */}
        <section className="bg-white border border-[#E2E8F0] rounded-xl overflow-hidden shadow-2xs flex flex-col">
          <div className="px-5 py-3.5 border-b border-[#E2E8F0] bg-[#F8FAFC] flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-[#16A34A]" />
              <h3 className="text-xs font-semibold uppercase tracking-wider text-[#0F172A]">
                Recent Automated Executions
              </h3>
              {executions.length > 0 && (
                <span className="text-[10px] font-mono font-medium px-2 py-0.5 bg-slate-100 border border-slate-200 text-slate-700 rounded-full">
                  {completed}/{executions.length}
                </span>
              )}
            </div>
            <button
              onClick={() => onNavigate("executions")}
              className="text-xs font-medium text-[#2563EB] hover:text-[#1D4ED8] transition cursor-pointer"
            >
              View all →
            </button>
          </div>

          <div className="divide-y divide-[#E2E8F0] overflow-y-auto flex-1">
            {historyLoading ? (
              <div className="p-5 space-y-3">
                {[...Array(3)].map((_, i) => (
                  <div key={i} className="flex items-center gap-3 animate-pulse">
                    <div className="h-5 w-16 bg-[#F1F5F9] rounded-full" />
                    <div className="h-4 flex-1 bg-[#F1F5F9] rounded" />
                    <div className="h-4 w-12 bg-[#F1F5F9] rounded" />
                  </div>
                ))}
              </div>
            ) : recentExecutions.length === 0 ? (
              <div className="py-12 text-center px-4">
                <div className="w-10 h-10 rounded-full bg-[#F1F5F9] text-[#94A3B8] flex items-center justify-center mx-auto mb-2">
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                  </svg>
                </div>
                <p className="text-xs font-medium text-[#0F172A]">No automation runs executed yet</p>
                <p className="text-[11px] text-[#64748B] mt-1">Approve a proposal or build a declarative workflow.</p>
                <button
                  onClick={() => onNavigate("discovery")}
                  className="mt-3 px-3 py-1.5 text-xs font-semibold rounded-lg bg-white border border-[#E2E8F0] text-[#0F172A] hover:bg-[#F8FAFC] shadow-2xs transition cursor-pointer"
                >
                  Review Discovered Workflows
                </button>
              </div>
            ) : (
              recentExecutions.map((ex) => {
                const cfg = statusBadgeConfig(ex.status);
                const progress =
                  ex.total_actions > 0
                    ? Math.round((ex.completed_actions.length / ex.total_actions) * 100)
                    : 0;
                return (
                  <div key={ex.execution_id} className="p-4 hover:bg-[#F8FAFC] transition">
                    <div className="flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-xs font-semibold text-[#0F172A] truncate">
                          {ex.workflow_name || "Automation Workflow"}
                        </p>
                        <p className="text-[11px] text-[#64748B] mt-0.5">
                          {ex.completed_actions.length}/{ex.total_actions} actions
                          {ex.execution_time_seconds != null && ` · ${ex.execution_time_seconds}s`}
                          {ex.applications && ex.applications.length > 0 && ` · ${ex.applications.map(getApplicationDisplayName).join(", ")}`}
                        </p>
                      </div>
                      <span className={`shrink-0 text-[10px] font-semibold px-2 py-0.5 rounded-full border ${cfg.className}`}>
                        {cfg.label}
                      </span>
                    </div>

                    {/* Progress Bar */}
                    <div className="mt-2.5 h-1.5 bg-[#F1F5F9] rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all duration-300 ${
                          ex.status === "completed"
                            ? "bg-[#16A34A]"
                            : ex.status === "failed"
                            ? "bg-[#DC2626]"
                            : ex.status === "paused"
                            ? "bg-[#F59E0B]"
                            : "bg-[#2563EB]"
                        }`}
                        style={{ width: `${progress}%` }}
                      />
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </section>
      </div>

      {/* Telemetry Summary Cards */}
      <section className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white border border-[#E2E8F0] rounded-xl p-4 shadow-2xs text-center">
          <div className="text-xl font-bold font-mono text-[#0F172A]">{failed}</div>
          <div className="text-[11px] font-medium text-[#64748B] mt-1">Failed / Paused Executions</div>
        </div>
        <div className="bg-white border border-[#E2E8F0] rounded-xl p-4 shadow-2xs text-center">
          <div className="text-xl font-bold font-mono text-[#0F172A]">
            {executions.reduce((s, e) => s + (e.execution_time_seconds ?? 0), 0).toFixed(1)}s
          </div>
          <div className="text-[11px] font-medium text-[#64748B] mt-1">Total Automation Runtime</div>
        </div>
        <div className="bg-white border border-[#E2E8F0] rounded-xl p-4 shadow-2xs text-center">
          <div className="text-xl font-bold font-mono text-[#0F172A]">
            {executions.reduce((s, e) => s + e.completed_actions.length, 0)}
          </div>
          <div className="text-[11px] font-medium text-[#64748B] mt-1">Total Actions Completed</div>
        </div>
      </section>
    </div>
  );
}
