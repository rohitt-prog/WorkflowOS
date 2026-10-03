"use client";

import React from "react";
import Link from "next/link";

export default function DemoOverviewPage() {
  return (
    <div className="space-y-6">
      {/* Overview Banner */}
      <div className="bg-white border border-[#E2E8F0] rounded-xl p-6 sm:p-8 relative overflow-hidden shadow-2xs">
        <div className="max-w-3xl">
          <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full text-xs font-mono bg-blue-50 text-[#2563EB] border border-blue-200 mb-3">
            <span className="w-1.5 h-1.5 rounded-full bg-[#2563EB] animate-pulse" />
            Phase 4.1 Controlled Target Applications
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-[#0F172A]">
            Automation Playground Applications
          </h1>
          <p className="text-xs sm:text-sm text-[#475569] mt-2 leading-relaxed">
            These mock applications provide isolated, deterministic environments
            for Playwright automated execution. They operate locally in client state
            without connecting to external SaaS or live enterprise credentials.
          </p>
        </div>
      </div>

      {/* Target Application Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Email App Card */}
        <div className="bg-white border border-[#E2E8F0] rounded-xl p-6 flex flex-col justify-between hover:shadow-xs hover:border-[#BFDBFE] transition group shadow-2xs">
          <div>
            <div className="w-10 h-10 rounded-xl bg-purple-50 border border-purple-200 text-purple-700 flex items-center justify-center mb-4">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
              </svg>
            </div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold text-[#0F172A]">WorkFlow Mail</h2>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#F1F5F9] text-[#64748B]">/demo/email</span>
            </div>
            <p className="text-xs text-[#475569] mt-2 leading-relaxed">
              Simulates incoming customer email from Rahul with an attached PDF document ready for extraction.
            </p>
            <div className="mt-4 space-y-1 text-[11px] font-mono text-[#64748B] bg-[#F8FAFC] p-3 rounded-lg border border-[#E2E8F0]">
              <div>• Steps: <span className="text-[#0F172A] font-semibold">open_email</span>, <span className="text-[#0F172A] font-semibold">download_attachment</span></div>
              <div>• Target: <span className="text-[#2563EB]">customer_request.pdf</span></div>
            </div>
          </div>
          <Link
            href="/demo/email"
            className="mt-6 inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold bg-[#2563EB] hover:bg-[#1D4ED8] text-white shadow-2xs transition active:scale-97"
          >
            Launch WorkFlow Mail
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
            </svg>
          </Link>
        </div>

        {/* CRM App Card */}
        <div className="bg-white border border-[#E2E8F0] rounded-xl p-6 flex flex-col justify-between hover:shadow-xs hover:border-[#BFDBFE] transition group shadow-2xs">
          <div>
            <div className="w-10 h-10 rounded-xl bg-sky-50 border border-sky-200 text-sky-700 flex items-center justify-center mb-4">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
              </svg>
            </div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold text-[#0F172A]">WorkFlow CRM</h2>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#F1F5F9] text-[#64748B]">/demo/crm</span>
            </div>
            <p className="text-xs text-[#475569] mt-2 leading-relaxed">
              Customer relationship management portal allowing search, account verification, and status updates.
            </p>
            <div className="mt-4 space-y-1 text-[11px] font-mono text-[#64748B] bg-[#F8FAFC] p-3 rounded-lg border border-[#E2E8F0]">
              <div>• Steps: <span className="text-[#0F172A] font-semibold">search_customer</span>, <span className="text-[#0F172A] font-semibold">update_customer</span></div>
              <div>• Target: <span className="text-[#2563EB]">Rahul Sharma (Enterprise)</span></div>
            </div>
          </div>
          <Link
            href="/demo/crm"
            className="mt-6 inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold bg-[#2563EB] hover:bg-[#1D4ED8] text-white shadow-2xs transition active:scale-97"
          >
            Launch WorkFlow CRM
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
            </svg>
          </Link>
        </div>

        {/* Chat App Card */}
        <div className="bg-white border border-[#E2E8F0] rounded-xl p-6 flex flex-col justify-between hover:shadow-xs hover:border-[#BFDBFE] transition group shadow-2xs">
          <div>
            <div className="w-10 h-10 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-700 flex items-center justify-center mb-4">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
              </svg>
            </div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold text-[#0F172A]">WorkFlow Chat</h2>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#F1F5F9] text-[#64748B]">/demo/chat</span>
            </div>
            <p className="text-xs text-[#475569] mt-2 leading-relaxed">
              Internal team messaging tool where automation posts execution confirmations and team alerts.
            </p>
            <div className="mt-4 space-y-1 text-[11px] font-mono text-[#64748B] bg-[#F8FAFC] p-3 rounded-lg border border-[#E2E8F0]">
              <div>• Steps: <span className="text-[#0F172A] font-semibold">send_message</span></div>
              <div>• Target: <span className="text-[#2563EB]">#customer-support</span></div>
            </div>
          </div>
          <Link
            href="/demo/chat"
            className="mt-6 inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold bg-[#2563EB] hover:bg-[#1D4ED8] text-white shadow-2xs transition active:scale-97"
          >
            Launch WorkFlow Chat
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M14 5l7 7m0 0l-7 7m7-7H3" />
            </svg>
          </Link>
        </div>
      </div>
    </div>
  );
}
