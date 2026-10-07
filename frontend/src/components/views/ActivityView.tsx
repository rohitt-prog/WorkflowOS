"use client";

import React, { useState, useMemo } from "react";
import { ActivityEvent } from "@/lib/types";
import { getAppBadgeClass, formatTimestamp, formatEventStep, getApplicationDisplayName } from "@/lib/utils";

interface ActivityViewProps {
  events: ActivityEvent[];
  loading: boolean;
}

export default function ActivityView({ events, loading }: ActivityViewProps) {
  const [searchTerm, setSearchTerm] = useState("");
  const [appFilter, setAppFilter] = useState("ALL");
  const [selectedEvent, setSelectedEvent] = useState<ActivityEvent | null>(null);

  const uniqueApps = useMemo(
    () => Array.from(new Set(events.map((e) => e.application))),
    [events]
  );

  const filteredEvents = useMemo(() => {
    return events.filter((ev) => {
      if (appFilter !== "ALL" && ev.application !== appFilter) return false;
      if (!searchTerm) return true;
      const term = searchTerm.toLowerCase();
      return (
        ev.application.toLowerCase().includes(term) ||
        ev.event_type.toLowerCase().includes(term) ||
        (ev.target || "").toLowerCase().includes(term) ||
        ev.session_id.toLowerCase().includes(term) ||
        JSON.stringify(ev.metadata || {}).toLowerCase().includes(term)
      );
    });
  }, [events, appFilter, searchTerm]);

  const getCustomer = (ev: ActivityEvent) =>
    ev.metadata?.customer ||
    ev.metadata?.customer_name ||
    ev.metadata?.client ||
    ev.metadata?.name ||
    null;

  return (
    <div className="flex flex-col h-full bg-[#F7F9FC]">
      {/* Controls Bar */}
      <div className="px-6 py-3.5 border-b border-[#E2E8F0] bg-white flex flex-wrap items-center justify-between gap-3 shadow-2xs shrink-0">
        <div className="flex items-center gap-3 flex-1 min-w-64 max-w-lg">
          {/* Search Box */}
          <div className="relative flex-1">
            <svg
              className="w-3.5 h-3.5 text-[#94A3B8] absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              type="text"
              placeholder="Search app, action, target, session ID…"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg pl-9 pr-8 py-1.5 text-xs text-[#0F172A] placeholder-[#94A3B8] focus:outline-none focus:border-[#2563EB] focus:bg-white transition"
            />
            {searchTerm && (
              <button
                onClick={() => setSearchTerm("")}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[#94A3B8] hover:text-[#0F172A] text-xs cursor-pointer"
              >
                ✕
              </button>
            )}
          </div>

          {/* App Filter Dropdown */}
          <select
            value={appFilter}
            onChange={(e) => setAppFilter(e.target.value)}
            className="bg-[#F8FAFC] border border-[#E2E8F0] text-[#0F172A] text-xs rounded-lg px-3 py-1.5 focus:outline-none focus:border-[#2563EB] focus:bg-white cursor-pointer"
          >
            <option value="ALL">All Applications ({uniqueApps.length})</option>
            {uniqueApps.map((app) => (
              <option key={app} value={app}>
                {getApplicationDisplayName(app)}
              </option>
            ))}
          </select>
        </div>

        {/* Counter */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-[#64748B] font-mono">
            Showing <strong className="text-[#0F172A]">{filteredEvents.length}</strong> of {events.length} events
          </span>
          {(searchTerm || appFilter !== "ALL") && (
            <button
              onClick={() => {
                setSearchTerm("");
                setAppFilter("ALL");
              }}
              className="text-xs text-[#2563EB] hover:underline cursor-pointer ml-1"
            >
              Reset
            </button>
          )}
        </div>
      </div>

      {/* Main Content Area: Table + Side Detail Drawer */}
      <div className="flex flex-1 overflow-hidden">
        {/* Event Table View */}
        <div className="flex-1 overflow-auto bg-white">
          {loading ? (
            <div className="p-6 space-y-3">
              {[...Array(8)].map((_, i) => (
                <div key={i} className="flex items-center gap-4 animate-pulse">
                  <div className="h-4 w-28 bg-[#F1F5F9] rounded" />
                  <div className="h-4 w-24 bg-[#F1F5F9] rounded" />
                  <div className="h-4 w-40 bg-[#F1F5F9] rounded" />
                  <div className="h-4 flex-1 bg-[#F1F5F9] rounded" />
                </div>
              ))}
            </div>
          ) : filteredEvents.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-80 text-center px-4">
              <div className="w-12 h-12 rounded-xl bg-[#F1F5F9] text-[#94A3B8] flex items-center justify-center mb-3">
                <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
              <h3 className="text-sm font-semibold text-[#0F172A]">
                {events.length === 0 ? "No activity events captured yet" : "No matching events found"}
              </h3>
              <p className="text-xs text-[#64748B] max-w-sm mt-1">
                {events.length === 0
                  ? "Start the macOS desktop activity agent with `python -m agent run` or trigger actions in demo apps."
                  : "Try clearing search filters or changing the selected application dropdown."}
              </p>
            </div>
          ) : (
            <table className="w-full text-left text-xs border-collapse">
              <thead className="bg-[#F8FAFC] text-[#64748B] font-semibold border-b border-[#E2E8F0] sticky top-0 z-10">
                <tr>
                  <th className="py-3 px-4 whitespace-nowrap">Timestamp</th>
                  <th className="py-3 px-4 whitespace-nowrap">Application</th>
                  <th className="py-3 px-4 whitespace-nowrap">Event Type</th>
                  <th className="py-3 px-4 whitespace-nowrap">Target</th>
                  <th className="py-3 px-4 whitespace-nowrap">Customer</th>
                  <th className="py-3 px-4 whitespace-nowrap text-right">Session</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E2E8F0]">
                {filteredEvents.map((ev) => {
                  const t = formatTimestamp(ev.timestamp);
                  const customer = getCustomer(ev);
                  const isSelected = selectedEvent?.id === ev.id;
                  const badgeClass = getAppBadgeClass(ev.application);
                  return (
                    <tr
                      key={ev.id}
                      onClick={() => setSelectedEvent(isSelected ? null : ev)}
                      className={`cursor-pointer transition-colors duration-150 animate-row-enter group ${
                        isSelected
                          ? "bg-[#EFF6FF] border-l-3 border-[#2563EB]"
                          : "hover:bg-[#F8FAFC]"
                      }`}
                    >
                      <td className="py-2.5 px-4 font-mono text-[#64748B] whitespace-nowrap">
                        <span title={t.full}>{t.relative || t.full}</span>
                      </td>
                      <td className="py-2.5 px-4 whitespace-nowrap">
                        <span className={`text-[10px] font-medium px-2 py-0.5 rounded border ${badgeClass}`}>
                          {getApplicationDisplayName(ev.application)}
                        </span>
                      </td>
                      <td className="py-2.5 px-4 whitespace-nowrap">
                        <span className="font-mono text-[#0F172A] font-semibold">
                          {formatEventStep(ev.event_type)}
                        </span>
                      </td>
                      <td className="py-2.5 px-4 max-w-xs truncate text-[#475569]">
                        {ev.target || <span className="text-[#94A3B8]">—</span>}
                      </td>
                      <td className="py-2.5 px-4 whitespace-nowrap text-[#475569]">
                        {customer ? (
                          <span className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-700 font-mono text-[10px]">
                            {customer}
                          </span>
                        ) : (
                          <span className="text-[#94A3B8]">—</span>
                        )}
                      </td>
                      <td className="py-2.5 px-4 font-mono text-[#94A3B8] text-right whitespace-nowrap">
                        <span title={ev.session_id}>
                          {ev.session_id ? `${ev.session_id.slice(0, 10)}…` : "—"}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>

        {/* Selected Event Detail Drawer */}
        {selectedEvent && (
          <aside className="w-96 border-l border-[#E2E8F0] bg-white flex flex-col h-full shadow-lg z-20 shrink-0 animate-fadeIn">
            {/* Drawer Header */}
            <div className="p-4 border-b border-[#E2E8F0] flex items-center justify-between bg-[#F8FAFC]">
              <div>
                <span className="text-[10px] font-semibold uppercase tracking-wider text-[#64748B]">
                  Event Details
                </span>
                <h4 className="text-sm font-bold text-[#0F172A]">
                  {formatEventStep(selectedEvent.event_type)}
                </h4>
              </div>
              <button
                onClick={() => setSelectedEvent(null)}
                className="text-[#94A3B8] hover:text-[#0F172A] p-1 rounded hover:bg-[#E2E8F0] transition cursor-pointer"
              >
                ✕
              </button>
            </div>

            {/* Drawer Body */}
            <div className="p-5 overflow-y-auto space-y-4 flex-1 text-xs">
              <div>
                <span className="text-[#64748B] block mb-1 font-medium">Application</span>
                <span className={`inline-block text-xs font-medium px-2 py-0.5 rounded border ${getAppBadgeClass(selectedEvent.application)}`}>
                  {getApplicationDisplayName(selectedEvent.application)} ({selectedEvent.application})
                </span>
              </div>

              <div>
                <span className="text-[#64748B] block mb-1 font-medium">Timestamp</span>
                <div className="font-mono text-[#0F172A] bg-[#F8FAFC] border border-[#E2E8F0] rounded p-2">
                  {selectedEvent.timestamp}
                </div>
              </div>

              {selectedEvent.target && (
                <div>
                  <span className="text-[#64748B] block mb-1 font-medium">Target Element / Resource</span>
                  <div className="font-mono text-[#0F172A] bg-[#F8FAFC] border border-[#E2E8F0] rounded p-2 break-all">
                    {selectedEvent.target}
                  </div>
                </div>
              )}

              <div>
                <span className="text-[#64748B] block mb-1 font-medium">Session ID</span>
                <div className="font-mono text-[#0F172A] bg-[#F8FAFC] border border-[#E2E8F0] rounded p-2 text-[11px] break-all">
                  {selectedEvent.session_id}
                </div>
              </div>

              <div>
                <span className="text-[#64748B] block mb-1 font-medium">Raw Metadata</span>
                <pre className="font-mono text-[11px] text-[#0F172A] bg-[#F8FAFC] border border-[#E2E8F0] rounded p-2.5 overflow-x-auto">
                  {JSON.stringify(selectedEvent.metadata || {}, null, 2)}
                </pre>
              </div>

              <div>
                <span className="text-[#64748B] block mb-1 font-medium">Full Event Object</span>
                <pre className="font-mono text-[11px] text-[#475569] bg-[#F8FAFC] border border-[#E2E8F0] rounded p-2.5 overflow-x-auto max-h-48">
                  {JSON.stringify(selectedEvent, null, 2)}
                </pre>
              </div>
            </div>
          </aside>
        )}
      </div>
    </div>
  );
}
