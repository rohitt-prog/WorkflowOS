"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

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
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col font-sans">
      {/* Top Demo Bar */}
      <header className="border-b border-zinc-800/80 bg-zinc-900/60 backdrop-blur-md sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          {/* Brand & Section Title */}
          <div className="flex items-center gap-3">
            <Link
              href="/"
              className="flex items-center gap-2.5 group transition"
              title="Return to WorkFlowOS Main Dashboard"
            >
              <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-cyan-600 via-indigo-600 to-purple-600 flex items-center justify-center shadow-lg shadow-cyan-900/30 ring-1 ring-white/10 group-hover:scale-105 transition-transform">
                <span className="text-white font-mono font-bold text-base tracking-tighter">W</span>
              </div>
              <div>
                <span className="text-sm font-bold tracking-tight text-white flex items-center gap-1">
                  WorkFlow<span className="text-cyan-400">OS</span>
                </span>
                <span className="text-[10px] text-zinc-500 block leading-tight font-mono">
                  Demo Environment
                </span>
              </div>
            </Link>

            <span className="text-zinc-700 hidden sm:inline">/</span>

            <span className="hidden sm:inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-mono bg-purple-950/50 text-purple-300 border border-purple-800/60">
              <span className="w-1.5 h-1.5 rounded-full bg-purple-400 animate-pulse"></span>
              Phase 4.1 Mock Apps
            </span>
          </div>

          {/* Navigation Tabs between Demo Apps */}
          <nav className="flex items-center gap-1 bg-zinc-950 p-1 rounded-xl border border-zinc-800" aria-label="Demo Applications">
            {navItems.map((item) => {
              const isActive = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                    isActive
                      ? "bg-indigo-600 text-white shadow-md shadow-indigo-950/60"
                      : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900"
                  }`}
                >
                  {item.icon}
                  <span>{item.name}</span>
                  <span
                    className={`hidden md:inline text-[9px] px-1.5 py-0.2 rounded font-mono ${
                      isActive
                        ? "bg-indigo-700 text-indigo-100"
                        : "bg-zinc-800/80 text-zinc-500"
                    }`}
                  >
                    {item.step}
                  </span>
                </Link>
              );
            })}
          </nav>

          {/* Return to Dashboard Link */}
          <div className="flex items-center gap-2">
            <Link
              href="/"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-zinc-800/80 hover:bg-zinc-700 text-zinc-300 border border-zinc-700 transition active:scale-95"
            >
              <svg className="w-3.5 h-3.5 text-zinc-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
              </svg>
              <span className="hidden sm:inline">Back to</span> Dashboard
            </Link>
          </div>
        </div>

        {/* Workflow Pipeline Breadcrumbs */}
        <div className="border-t border-zinc-800/60 bg-zinc-950/60 py-1.5 px-4 overflow-x-auto text-[11px] font-mono text-zinc-400">
          <div className="max-w-7xl mx-auto flex items-center gap-2 min-w-max">
            <span className="text-zinc-500 uppercase tracking-wider text-[10px] font-semibold">Workflow Target:</span>
            <span className={`px-2 py-0.5 rounded ${pathname === "/demo/email" ? "bg-indigo-950 text-indigo-300 border border-indigo-800 font-bold" : "bg-zinc-900 text-zinc-400"}`}>
              1. open_email
            </span>
            <span className="text-zinc-600">→</span>
            <span className={`px-2 py-0.5 rounded ${pathname === "/demo/email" ? "bg-indigo-950 text-indigo-300 border border-indigo-800 font-bold" : "bg-zinc-900 text-zinc-400"}`}>
              2. download_attachment
            </span>
            <span className="text-zinc-600">→</span>
            <span className={`px-2 py-0.5 rounded ${pathname === "/demo/crm" ? "bg-indigo-950 text-indigo-300 border border-indigo-800 font-bold" : "bg-zinc-900 text-zinc-400"}`}>
              3. search_customer
            </span>
            <span className="text-zinc-600">→</span>
            <span className={`px-2 py-0.5 rounded ${pathname === "/demo/crm" ? "bg-indigo-950 text-indigo-300 border border-indigo-800 font-bold" : "bg-zinc-900 text-zinc-400"}`}>
              4. update_customer
            </span>
            <span className="text-zinc-600">→</span>
            <span className={`px-2 py-0.5 rounded ${pathname === "/demo/chat" ? "bg-indigo-950 text-indigo-300 border border-indigo-800 font-bold" : "bg-zinc-900 text-zinc-400"}`}>
              5. send_message
            </span>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {children}
      </main>

      {/* Demo Footer */}
      <footer className="border-t border-zinc-800/80 bg-zinc-950 text-zinc-500 text-xs py-4 mt-auto">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-2">
          <p>© 2026 WorkFlowOS. Phase 4.1 — Controlled Automation Sandbox Environment.</p>
          <div className="flex items-center gap-4 text-[11px] font-mono text-zinc-500">
            <span>Mock Applications: Email • CRM • Chat</span>
            <span>•</span>
            <span className="text-emerald-400/80">Playwright-Ready Selectors</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
