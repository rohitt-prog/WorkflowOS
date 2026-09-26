"use client";

import React from "react";
import Link from "next/link";

export default function DemoOverviewPage() {
  return (
    <div className="space-y-6">
      {/* Overview Banner */}
      <div className="bg-zinc-900/60 border border-zinc-800/80 rounded-2xl p-6 sm:p-8 relative overflow-hidden shadow-lg">
        <div className="absolute top-0 right-0 w-80 h-80 bg-gradient-to-br from-indigo-500/10 via-cyan-500/10 to-transparent rounded-full blur-3xl pointer-events-none" />
        <div className="max-w-3xl">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-mono bg-indigo-950/60 text-indigo-300 border border-indigo-800/60 mb-3">
            <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse"></span>
            Phase 4.1 — Controlled Target Applications
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-white">
            Automation Playground Applications
          </h1>
          <p className="text-sm text-zinc-400 mt-2 leading-relaxed">
            These realistic mock applications provide isolated, deterministic environments
            for Playwright automated execution in Phase 4. They operate entirely in local state
            without connecting to external SaaS or live enterprise credentials.
          </p>
        </div>
      </div>

      {/* Target Application Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Email App Card */}
        <div className="bg-zinc-900/50 border border-zinc-800/80 rounded-xl p-6 flex flex-col justify-between hover:border-indigo-600/60 transition group">
          <div>
            <div className="w-10 h-10 rounded-xl bg-purple-950/70 border border-purple-800/70 text-purple-300 flex items-center justify-center mb-4">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
              </svg>
            </div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-bold text-white">WorkFlow Mail</h2>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-800 text-zinc-400">/demo/email</span>
            </div>
            <p className="text-xs text-zinc-400 mt-2">
              Simulates incoming customer email from Rahul with an attached PDF document ready for extraction.
            </p>
            <div className="mt-4 space-y-1.5 text-[11px] font-mono text-zinc-500">
              <div>• Steps: <span className="text-zinc-300">open_email</span>, <span className="text-zinc-300">download_attachment</span></div>
              <div>• Target: <span className="text-zinc-300">customer_request.pdf</span></div>
            </div>
          </div>
          <Link
            href="/demo/email"
            className="mt-6 inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white transition active:scale-95 shadow-md shadow-indigo-950"
          >
            Launch WorkFlow Mail
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
            </svg>
          </Link>
        </div>

        {/* CRM App Card */}
        <div className="bg-zinc-900/50 border border-zinc-800/80 rounded-xl p-6 flex flex-col justify-between hover:border-cyan-600/60 transition group">
          <div>
            <div className="w-10 h-10 rounded-xl bg-sky-950/70 border border-sky-800/70 text-sky-300 flex items-center justify-center mb-4">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
              </svg>
            </div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-bold text-white">WorkFlow CRM</h2>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-800 text-zinc-400">/demo/crm</span>
            </div>
            <p className="text-xs text-zinc-400 mt-2">
              Customer database with search, profile view, field editing, and deterministic &quot;Unknown Customer&quot; fallback.
            </p>
            <div className="mt-4 space-y-1.5 text-[11px] font-mono text-zinc-500">
              <div>• Steps: <span className="text-zinc-300">search_customer</span>, <span className="text-zinc-300">update_customer</span></div>
              <div>• Seed: <span className="text-zinc-300">Rahul (Active)</span></div>
            </div>
          </div>
          <Link
            href="/demo/crm"
            className="mt-6 inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold bg-cyan-600 hover:bg-cyan-500 text-white transition active:scale-95 shadow-md shadow-cyan-950"
          >
            Launch WorkFlow CRM
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
            </svg>
          </Link>
        </div>

        {/* Chat App Card */}
        <div className="bg-zinc-900/50 border border-zinc-800/80 rounded-xl p-6 flex flex-col justify-between hover:border-emerald-600/60 transition group">
          <div>
            <div className="w-10 h-10 rounded-xl bg-emerald-950/70 border border-emerald-800/70 text-emerald-300 flex items-center justify-center mb-4">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
              </svg>
            </div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-bold text-white">WorkFlow Chat</h2>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-800 text-zinc-400">/demo/chat</span>
            </div>
            <p className="text-xs text-zinc-400 mt-2">
              Internal messaging app for team notifications with channel selection and instant message delivery confirmation.
            </p>
            <div className="mt-4 space-y-1.5 text-[11px] font-mono text-zinc-500">
              <div>• Step: <span className="text-zinc-300">send_message</span></div>
              <div>• Channel: <span className="text-zinc-300">#customer-support</span></div>
            </div>
          </div>
          <Link
            href="/demo/chat"
            className="mt-6 inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white transition active:scale-95 shadow-md shadow-emerald-950"
          >
            Launch WorkFlow Chat
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
            </svg>
          </Link>
        </div>
      </div>
    </div>
  );
}
