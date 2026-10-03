"use client";

import React, { useState, useMemo } from "react";
import { ActivityEvent } from "@/lib/types";
import { getAppBadgeClass, formatTimestamp } from "@/lib/utils";

interface ActivityViewProps {
  events: ActivityEvent[];
  loading: boolean;
}

export default function ActivityView({ events, loading }: ActivityViewProps) {
  const [searchTerm, setSearchTerm] = useState("");
  const [appFilter, setAppFilter] = useState("ALL");
  const [selectedEvent, setSelectedEvent] = useState<ActivityEvent | null>(null);

  const uniqueApps = useMemo(() => Array.from(new Set(events.map((e) => e.application))), [events]);

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
    ev.metadata?.customer || ev.metadata?.customer_name || ev.metadata?.client || ev.metadata?.name || null;

  return (
    <div className="flex flex-col h-full">
      {/* Controls Bar */}
      <div className="px-6 py-3 border-b border-zinc-800/60 bg-zinc-900/40 flex flex-wrap items-center gap-3">
        {/* Search */}
        <div className="relative flex-1 min-w-48 max-w-sm">
          <svg className="w-3.5 h-3.5 text-zinc-500 absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            placeholder="Search app, event, target, session…"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full bg-zinc-950 border border-zinc-800 rounded-lg pl-8 pr-7 py-1.5 text-xs text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50 transition"
          />
          {searchTerm && (
            <button
              onClick={() => setSearchTerm("")}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300 text-xs"
            >✕</button>
          )}
        </div>

        {/* App filter */}
        <select
          value={appFilter}
          onChange={(e) => setAppFilter(e.target.value)}
          className="bg-zinc-950 border border-zinc-800 text-zinc-300 text-xs rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-indigo-500 cursor-pointer"
        >
          <option value="ALL">All Applications</option>
          {uniqueApps.map((app) => <option key={app} value={app}>{app}</option>)}
        </select>

        {/* Count */}
        <span className="text-[11px] text-zinc-500 font-mono ml-auto">
          {filteredEvents.length} / {events.length} events
        </span>
      </div>

      {/* Main content: table + detail panel */}
      <div className="flex flex-1 overflow-hidden">
        {/* Table */}
        <div className={`flex-1 overflow-auto ${selectedEvent ? "border-r border-zinc-800/60" : ""}`}>
          {loading ? (
            <div className="p-6 space-y-3">
              {[...Array(8)].map((_, i) => (
                <div key={i} className="flex gap-4 animate-pulse">
                  <div className="h-4 w-28 bg-zinc-800 rounded" />
                  <div className="h-4 w-24 bg-zinc-800 rounded" />
                  <div className="h-4 w-32 bg-zinc-800 rounded" />
                  <div className="h-4 w-36 bg-zinc-800 rounded" />
                </div>
              ))}
            </div>
          ) : filteredEvents.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-64 text-center px-6">
              <div className="w-12 h-12 rounded-xl bg-zinc-800/60 border border-zinc-700/50 flex items-center justify-center mb-3 text-zinc-500">
                <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
                </svg>
              </div>
              <p className="text-sm font-medium text-zinc-300">
                {events.length === 0 ? "No activity events yet" : "No matching events"}
              </p>
              <p className="text-xs text-zinc-500 mt-1 max-w-xs">
                {events.length === 0
                  ? "Start the desktop agent or run: python backend/test_event.py --all"
                  : "Try adjusting search or app filter."}
              </p>
            </div>
          ) : (
            <table className="w-full text-left text-xs">
              <thead className="sticky top-0 z-10">
                <tr className="bg-zinc-950 border-b border-zinc-800/80 text-zinc-500 font-medium">
                  <th className="py-2.5 px-4 whitespace-nowrap">Time</th>
                  <th className="py-2.5 px-4 whitespace-nowrap">Application</th>
                  <th className="py-2.5 px-4 whitespace-nowrap">Event Type</th>
                  <th className="py-2.5 px-4 whitespace-nowrap">Target</th>
                  <th className="py-2.5 px-4 whitespace-nowrap">Customer</th>
                  <th className="py-2.5 px-4 whitespace-nowrap text-right">Session</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/50">
                {filteredEvents.map((ev) => {
                  const t = formatTimestamp(ev.timestamp);
                  const customer = getCustomer(ev);
                  const isSelected = selectedEvent?.id === ev.id;
                  return (
                    <tr
                      key={ev.id}
                      onClick={() => setSelectedEvent(isSelected ? null : ev)}
                      className={`cursor-pointer transition group ${
                        isSelected ? "bg-indigo-950/40 border-l-2 border-indigo-500" : "hover:bg-zinc-800/25"
                      }`}
                    >
                      <td className="py-2.5 px-4 whitespace-nowrap">
                        <div className="font-mono text-zinc-300">{t.full}</div>
                        {t.relative && <div className="text-[10px] text-zinc-600">{t.relative}</div>}
                      </td>
                      <td className="py-2.5 px-4 whitespace-nowrap">
                        <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-mono border ${getAppBadgeClass(ev.application)}`}>
                          {ev.application}
                        </span>
                      </td>
                      <td className="py-2.5 px-4 whitespace-nowrap">
                        <span className="font-mono font-medium text-cyan-300 bg-cyan-950/30 px-2 py-0.5 rounded border border-cyan-800/40">
                          {ev.event_type}
                        </span>
                      </td>
                      <td className="py-2.5 px-4 max-w-[180px] truncate text-zinc-300 font-mono">
                        {ev.target ? <span title={ev.target}>{ev.target}</span> : <span className="text-zinc-700">—</span>}
                      </td>
                      <td className="py-2.5 px-4 whitespace-nowrap text-zinc-400">
                        {customer || <span className="text-zinc-700">—</span>}
                      </td>
                      <td className="py-2.5 px-4 whitespace-nowrap text-right">
                        <code className="text-[10px] font-mono text-zinc-600 bg-zinc-900 px-1.5 py-0.5 rounded border border-zinc-800">
                          {ev.session_id.slice(0, 12)}…
                        </code>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>

        {/* Detail panel */}
        {selectedEvent && (
          <div className="w-72 shrink-0 overflow-y-auto bg-zinc-950/80 border-l border-zinc-800/60 p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-white">Event Detail</h3>
              <button
                onClick={() => setSelectedEvent(null)}
                className="text-zinc-500 hover:text-zinc-300 transition text-lg leading-none cursor-pointer"
              >×</button>
            </div>
            <div className="space-y-4 text-xs">
              <div>
                <p className="text-zinc-500 uppercase tracking-wider text-[10px] font-semibold mb-1">Event Type</p>
                <span className="font-mono font-medium text-cyan-300 bg-cyan-950/30 px-2 py-0.5 rounded border border-cyan-800/40">
                  {selectedEvent.event_type}
                </span>
              </div>
              <div>
                <p className="text-zinc-500 uppercase tracking-wider text-[10px] font-semibold mb-1">Application</p>
                <span className={`inline-flex items-center px-2 py-0.5 rounded font-mono border ${getAppBadgeClass(selectedEvent.application)}`}>
                  {selectedEvent.application}
                </span>
              </div>
              <div>
                <p className="text-zinc-500 uppercase tracking-wider text-[10px] font-semibold mb-1">Timestamp</p>
                <p className="text-zinc-300 font-mono">{new Date(selectedEvent.timestamp).toLocaleString()}</p>
              </div>
              {selectedEvent.target && (
                <div>
                  <p className="text-zinc-500 uppercase tracking-wider text-[10px] font-semibold mb-1">Target</p>
                  <p className="text-zinc-300 font-mono break-all">{selectedEvent.target}</p>
                </div>
              )}
              <div>
                <p className="text-zinc-500 uppercase tracking-wider text-[10px] font-semibold mb-1">Session ID</p>
                <p className="text-zinc-400 font-mono break-all">{selectedEvent.session_id}</p>
              </div>
              <div>
                <p className="text-zinc-500 uppercase tracking-wider text-[10px] font-semibold mb-1">Event ID</p>
                <p className="text-zinc-600 font-mono break-all">{selectedEvent.id}</p>
              </div>
              {selectedEvent.metadata && Object.keys(selectedEvent.metadata).length > 0 && (
                <div>
                  <p className="text-zinc-500 uppercase tracking-wider text-[10px] font-semibold mb-1">Metadata</p>
                  <pre className="text-zinc-400 font-mono text-[10px] bg-zinc-900 border border-zinc-800 rounded p-2.5 overflow-x-auto whitespace-pre-wrap break-all">
                    {JSON.stringify(selectedEvent.metadata, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
