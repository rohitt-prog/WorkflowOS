"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import Sidebar from "@/components/Sidebar";
import ThemeToggle from "@/components/ThemeToggle";

export default function DemoLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();

  const navItems = [
    {
      name: "Mail",
      href: "/demo/email",
      step: "Steps 1–2",
      icon: (
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
          />
        </svg>
      ),
    },
    {
      name: "CRM",
      href: "/demo/crm",
      step: "Steps 3–4",
      icon: (
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"
          />
        </svg>
      ),
    },
    {
      name: "Chat",
      href: "/demo/chat",
      step: "Step 5",
      icon: (
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
          />
        </svg>
      ),
    },
  ];

  return (
    <div className="min-h-screen bg-[#F7F9FC] dark:bg-[#0B0F17] text-[#475569] dark:text-[#94A3B8] flex font-sans">
      {/* Global Shared Sidebar in Auto-Hide Mode for Demo Applications */}
      <Sidebar activeView="demo" />

      {/* Main App Canvas */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top Demo Bar */}
        <header className="border-b border-[#E2E8F0] dark:border-[#1E293B] bg-white dark:bg-[#111827] sticky top-0 z-30 shadow-2xs transition-colors duration-150">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
            {/* Brand & Section Title - Logo navigates to Overview */}
            <div className="flex items-center gap-3">
              <Link
                href="/"
                className="flex items-center gap-2.5 group transition-colors duration-150 cursor-pointer"
                title="Return to WorkFlowOS Overview"
              >
                <div className="w-8 h-8 rounded-lg bg-[#2563EB] flex items-center justify-center text-white shadow-xs shrink-0">
                  <svg className="w-4.5 h-4.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                </div>
                <div>
                  <span className="text-sm font-bold tracking-tight text-[#0F172A] dark:text-[#F8FAFC] flex items-center gap-1 group-hover:text-[#2563EB] dark:group-hover:text-[#60A5FA] transition-colors duration-150">
                    WorkFlow<span className="text-[#2563EB] dark:text-[#3B82F6]">OS</span>
                  </span>
                  <span className="text-[10px] text-[#64748B] dark:text-[#94A3B8] block leading-tight font-mono">
                    Demo Playground
                  </span>
                </div>
              </Link>

              <span className="text-[#CBD5E1] dark:text-[#334155] hidden sm:inline">/</span>

              <span className="hidden sm:inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-mono bg-purple-50 dark:bg-purple-950/40 text-purple-700 dark:text-purple-300 border border-purple-200 dark:border-purple-800/60">
                <span className="w-1.5 h-1.5 rounded-full bg-purple-500 animate-pulse" />
                Target Test Apps
              </span>
            </div>

            {/* Navigation Tabs between Demo Apps */}
            <nav className="flex items-center gap-1 bg-[#F8FAFC] dark:bg-[#162035] p-1 rounded-xl border border-[#E2E8F0] dark:border-[#1E293B]" aria-label="Demo Applications">
              {navItems.map((item) => {
                const isActive = pathname === item.href;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors duration-150 cursor-pointer ${
                      isActive
                        ? "bg-white dark:bg-[#111827] text-[#1D4ED8] dark:text-[#60A5FA] font-semibold shadow-2xs border border-[#BFDBFE] dark:border-[#2563EB]/40"
                        : "text-[#64748B] dark:text-[#94A3B8] hover:text-[#0F172A] dark:hover:text-[#F8FAFC] hover:bg-white/60 dark:hover:bg-white/5"
                    }`}
                  >
                    <span className={isActive ? "text-[#2563EB] dark:text-[#60A5FA]" : "text-[#94A3B8] dark:text-[#64748B]"}>{item.icon}</span>
                    <span>{item.name}</span>
                    <span className={`text-[10px] font-mono px-1 rounded ${isActive ? "bg-blue-50 dark:bg-[#1E293B] text-[#2563EB] dark:text-[#60A5FA]" : "text-[#94A3B8] dark:text-[#64748B]"}`}>
                      {item.step}
                    </span>
                  </Link>
                );
              })}
            </nav>

            {/* Return to Dashboard and Theme Toggle */}
            <div className="flex items-center gap-2.5">
              <ThemeToggle />
              <Link
                href="/"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-white dark:bg-[#162035] hover:bg-[#F8FAFC] dark:hover:bg-[#1E293B] hover:shadow-xs border border-[#E2E8F0] dark:border-[#1E293B] text-[#0F172A] dark:text-[#F8FAFC] shadow-2xs transition-colors duration-150 cursor-pointer"
              >
                <svg className="w-3.5 h-3.5 text-[#64748B] dark:text-[#94A3B8]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
                </svg>
                <span>Back to Overview</span>
              </Link>
            </div>
          </div>
        </header>

        {/* Main Page Body */}
        <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
          {children}
        </main>
      </div>
    </div>
  );
}
