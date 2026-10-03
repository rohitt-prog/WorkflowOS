"use client";

import React from "react";
import Link from "next/link";
import { ViewId } from "@/lib/types";

interface NavItem {
  id: ViewId;
  label: string;
  icon: React.ReactNode;
  badge?: number | string;
}

interface SidebarProps {
  activeView: ViewId;
  onNavigate: (view: ViewId) => void;
  backendStatus: "connected" | "disconnected" | "checking";
  eventCount: number;
  executionCount: number;
  discoveryCount: number;
}

const IconDashboard = () => (
  <svg className="w-4.5 h-4.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
  </svg>
);

const IconActivity = () => (
  <svg className="w-4.5 h-4.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
  </svg>
);

const IconDiscovery = () => (
  <svg className="w-4.5 h-4.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2m0 10V7m0 10a2 2 0 002 2h2a2 2 0 002-2V7a2 2 0 00-2-2h-2a2 2 0 00-2 2" />
  </svg>
);

const IconBuilder = () => (
  <svg className="w-4.5 h-4.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />
  </svg>
);

const IconExecutions = () => (
  <svg className="w-4.5 h-4.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" />
  </svg>
);

const IconSettings = () => (
  <svg className="w-4.5 h-4.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
    <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
  </svg>
);

export default function Sidebar({
  activeView,
  onNavigate,
  backendStatus,
  eventCount,
  executionCount,
  discoveryCount,
}: SidebarProps) {
  const navItems: NavItem[] = [
    { id: "dashboard", label: "Dashboard", icon: <IconDashboard /> },
    { id: "activity", label: "Activity Feed", icon: <IconActivity />, badge: eventCount > 0 ? eventCount : undefined },
    { id: "discovery", label: "Discovery", icon: <IconDiscovery />, badge: discoveryCount > 0 ? discoveryCount : undefined },
    { id: "builder", label: "Workflow Builder", icon: <IconBuilder /> },
    { id: "executions", label: "Executions", icon: <IconExecutions />, badge: executionCount > 0 ? executionCount : undefined },
    { id: "settings", label: "Settings", icon: <IconSettings /> },
  ];

  return (
    <aside className="w-56 shrink-0 bg-zinc-900/60 border-r border-zinc-800/80 flex flex-col h-screen sticky top-0">
      {/* Logo / Brand */}
      <div className="h-14 px-4 flex items-center border-b border-zinc-800/60 gap-2.5 shrink-0">
        <div className="w-7 h-7 rounded-lg bg-gradient-to-tr from-cyan-600 via-indigo-600 to-purple-600 flex items-center justify-center shadow-lg shadow-cyan-900/30 ring-1 ring-white/10 shrink-0">
          <span className="text-white font-mono font-bold text-sm">W</span>
        </div>
        <div>
          <div className="text-sm font-bold tracking-tight text-white leading-tight">
            WorkFlow<span className="text-cyan-400">OS</span>
          </div>
          <div className="text-[10px] text-zinc-500 leading-tight">Phase 6</div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-3 px-2 space-y-0.5 overflow-y-auto">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-600 px-2 pb-2 pt-1">Navigation</p>
        {navItems.map((item) => {
          const isActive = activeView === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              className={`w-full flex items-center justify-between gap-2.5 px-3 py-2 rounded-lg text-sm font-medium transition-all cursor-pointer group
                ${isActive
                  ? "bg-indigo-950/80 text-indigo-300 border border-indigo-700/50"
                  : "text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800/60 border border-transparent"
                }`}
            >
              <span className="flex items-center gap-2.5">
                <span className={isActive ? "text-indigo-400" : "text-zinc-500 group-hover:text-zinc-300"}>
                  {item.icon}
                </span>
                {item.label}
              </span>
              {item.badge !== undefined && (
                <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded-full border min-w-[20px] text-center
                  ${isActive
                    ? "bg-indigo-900/60 border-indigo-600/60 text-indigo-300"
                    : "bg-zinc-800 border-zinc-700 text-zinc-400"
                  }`}>
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}

        {/* Demo Apps link */}
        <div className="pt-3">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-600 px-2 pb-2">Tools</p>
          <Link
            href="/demo"
            className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800/60 border border-transparent transition-all cursor-pointer"
          >
            <svg className="w-4.5 h-4.5 text-zinc-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
            </svg>
            Demo Apps
          </Link>
        </div>
      </nav>

      {/* Backend status footer */}
      <div className="px-3 py-3 border-t border-zinc-800/60 shrink-0">
        <div className={`flex items-center gap-2 px-2.5 py-2 rounded-lg text-xs border transition-all
          ${backendStatus === "connected"
            ? "bg-emerald-950/40 border-emerald-800/40 text-emerald-400"
            : backendStatus === "checking"
            ? "bg-amber-950/40 border-amber-800/40 text-amber-400"
            : "bg-rose-950/40 border-rose-800/40 text-rose-400"
          }`}>
          <span className="relative flex h-2 w-2 shrink-0">
            {backendStatus === "connected" && (
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
            )}
            <span className={`relative inline-flex rounded-full h-2 w-2 ${
              backendStatus === "connected" ? "bg-emerald-500"
              : backendStatus === "checking" ? "bg-amber-500"
              : "bg-rose-500"
            }`} />
          </span>
          <div>
            <div className="font-medium leading-tight">API Backend</div>
            <div className="text-[10px] opacity-70 capitalize">{backendStatus}</div>
          </div>
        </div>
      </div>
    </aside>
  );
}
