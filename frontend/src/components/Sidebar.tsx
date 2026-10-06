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
  <svg className="w-4.5 h-4.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
  </svg>
);

const IconActivity = () => (
  <svg className="w-4.5 h-4.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
  </svg>
);

const IconDiscovery = () => (
  <svg className="w-4.5 h-4.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
  </svg>
);


const IconExecutions = () => (
  <svg className="w-4.5 h-4.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" />
  </svg>
);

const IconApplications = () => (
  <svg className="w-4.5 h-4.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
  </svg>
);

const IconSettings = () => (
  <svg className="w-4.5 h-4.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
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
    { id: "dashboard", label: "Overview", icon: <IconDashboard /> },
    {
      id: "activity",
      label: "Activity",
      icon: <IconActivity />,
      badge: eventCount > 0 ? eventCount : undefined,
    },
    {
      id: "workflows",
      label: "Workflows",
      icon: <IconDiscovery />,
      badge: discoveryCount > 0 ? discoveryCount : undefined,
    },
    { id: "applications", label: "Applications", icon: <IconApplications /> },
    {
      id: "executions",
      label: "Executions",
      icon: <IconExecutions />,
      badge: executionCount > 0 ? executionCount : undefined,
    },
    { id: "settings", label: "Settings", icon: <IconSettings /> },
  ];

  return (
    <aside className="w-60 shrink-0 bg-white border-r border-[#E2E8F0] flex flex-col h-screen sticky top-0 z-30 select-none">
      {/* Brand Header */}
      <div className="h-16 px-5 flex items-center border-b border-[#E2E8F0] gap-3 shrink-0">
        <div className="w-8 h-8 rounded-lg bg-[#2563EB] flex items-center justify-center text-white shadow-xs shrink-0">
          <svg className="w-4.5 h-4.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
        </div>
        <div className="min-w-0">
          <div className="flex items-center gap-1.5">
            <span className="text-sm font-bold tracking-tight text-[#0F172A] leading-none">
              WorkFlow<span className="text-[#2563EB]">OS</span>
            </span>
            <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-[#DBEAFE] text-[#1D4ED8] font-mono leading-none">
              v1.0
            </span>
          </div>
          <p className="text-[11px] text-[#475569] leading-tight mt-1 truncate">
            Intelligent Automation
          </p>
        </div>
      </div>

      {/* Navigation Groups */}
      <nav className="flex-1 py-4 px-3 space-y-6 overflow-y-auto">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wider text-[#94A3B8] px-2.5 pb-2">
            Navigation
          </p>
          <div className="space-y-1">
            {navItems.map((item) => {
              const isActive =
                activeView === item.id ||
                (item.id === "workflows" && (activeView === "discovery" || activeView === "builder"));
              return (
                <button
                  key={item.id}
                  onClick={() => onNavigate(item.id)}
                  className={`w-full flex items-center justify-between gap-3 px-3 py-2 rounded-lg text-xs font-medium transition-all cursor-pointer text-left
                    ${
                      isActive
                        ? "bg-[#DBEAFE] text-[#1D4ED8] font-semibold shadow-2xs"
                        : "text-[#475569] hover:text-[#0F172A] hover:bg-[#F8FAFC]"
                    }`}
                >
                  <span className="flex items-center gap-2.5 truncate">
                    <span className={isActive ? "text-[#2563EB]" : "text-[#64748B]"}>
                      {item.icon}
                    </span>
                    <span className="truncate">{item.label}</span>
                  </span>
                  {item.badge !== undefined && (
                    <span
                      className={`text-[10px] font-mono px-2 py-0.5 rounded-full border min-w-[20px] text-center shrink-0
                        ${
                          isActive
                            ? "bg-white text-[#1D4ED8] border-[#BFDBFE] font-bold"
                            : "bg-[#F1F5F9] text-[#64748B] border-[#E2E8F0]"
                        }`}
                    >
                      {item.badge}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {/* Tools Group */}
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wider text-[#94A3B8] px-2.5 pb-2">
            Playground
          </p>
          <div className="space-y-1">
            <Link
              href="/demo"
              className="w-full flex items-center justify-between gap-3 px-3 py-2 rounded-lg text-xs font-medium text-[#475569] hover:text-[#0F172A] hover:bg-[#F8FAFC] transition cursor-pointer"
            >
              <span className="flex items-center gap-2.5">
                <svg className="w-4.5 h-4.5 text-[#64748B]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                </svg>
                <span>Demo Applications</span>
              </span>
              <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 border border-slate-200">
                3 Apps
              </span>
            </Link>
          </div>
        </div>
      </nav>

      {/* Backend Status Footer */}
      <div className="p-3 border-t border-[#E2E8F0] bg-[#F8FAFC] shrink-0">
        <div className="flex items-center justify-between p-2.5 rounded-lg border border-[#E2E8F0] bg-white shadow-2xs">
          <div className="flex items-center gap-2.5 min-w-0">
            <span className="relative flex h-2 w-2 shrink-0">
              {backendStatus === "connected" && (
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#10B981] opacity-75" />
              )}
              <span
                className={`relative inline-flex rounded-full h-2 w-2 ${
                  backendStatus === "connected"
                    ? "bg-[#10B981]"
                    : backendStatus === "checking"
                    ? "bg-[#F59E0B]"
                    : "bg-[#DC2626]"
                }`}
              />
            </span>
            <div className="min-w-0">
              <div className="text-xs font-semibold text-[#0F172A] truncate">
                Backend API
              </div>
              <div className="text-[10px] text-[#475569] capitalize">
                {backendStatus}
              </div>
            </div>
          </div>
          <span className="text-[10px] font-mono text-[#94A3B8]">
            :8000
          </span>
        </div>
      </div>
    </aside>
  );
}
