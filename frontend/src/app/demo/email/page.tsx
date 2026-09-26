"use client";

import React, { useState } from "react";

interface EmailItem {
  id: string;
  senderName: string;
  senderEmail: string;
  subject: string;
  preview: string;
  timestamp: string;
  hasAttachment: boolean;
  attachmentName?: string;
  attachmentSize?: string;
  body: string;
  isUnread?: boolean;
}

const SEED_EMAILS: EmailItem[] = [
  {
    id: "email_001",
    senderName: "Rahul",
    senderEmail: "rahul@example.com",
    subject: "Urgent: Customer Account Verification & Request",
    preview: "Please find attached the customer account verification request document...",
    timestamp: "10:30 AM",
    hasAttachment: true,
    attachmentName: "customer_request.pdf",
    attachmentSize: "245 KB",
    body: `Hello Support Team,

Please find attached our official customer request document (customer_request.pdf).
We need our CRM profile updated with high-priority enterprise support status, and a confirmation sent to our account manager.

Details in attached file:
- Customer Name: Rahul Sharma
- Company: Rahul Enterprises
- Target Tier: VIP Enterprise
- Action: Update status and notify team

Best regards,
Rahul
VP of Operations`,
    isUnread: true,
  },
  {
    id: "email_002",
    senderName: "Cloud Infrastructure",
    senderEmail: "alerts@cloudservice.internal",
    subject: "Daily Storage & Index Health Report",
    preview: "All database instances healthy across primary and replica nodes...",
    timestamp: "09:15 AM",
    hasAttachment: false,
    body: "Automated daily backup completed successfully. 0 errors detected.",
    isUnread: false,
  },
  {
    id: "email_003",
    senderName: "Customer Success",
    senderEmail: "cs-lead@workflowos.io",
    subject: "Weekly Onboarding Pipeline Review",
    preview: "Attached are the onboarding metrics for current cohort...",
    timestamp: "Yesterday",
    hasAttachment: false,
    body: "Hi team, please review this week's onboarding figures prior to tomorrow's sync.",
    isUnread: false,
  },
];

export default function DemoEmailPage() {
  const [emails, setEmails] = useState<EmailItem[]>(SEED_EMAILS);
  const [selectedEmailId, setSelectedEmailId] = useState<string | null>(null);
  const [downloadedAttachments, setDownloadedAttachments] = useState<Record<string, boolean>>({});

  const selectedEmail = emails.find((e) => e.id === selectedEmailId) || null;

  const handleOpenEmail = (id: string) => {
    setSelectedEmailId(id);
    // Mark as read
    setEmails((prev) =>
      prev.map((e) => (e.id === id ? { ...e, isUnread: false } : e))
    );
  };

  const handleDownloadAttachment = (attachmentName: string) => {
    setDownloadedAttachments((prev) => ({
      ...prev,
      [attachmentName]: true,
    }));
  };

  const handleResetAttachment = (attachmentName: string) => {
    setDownloadedAttachments((prev) => ({
      ...prev,
      [attachmentName]: false,
    }));
  };

  return (
    <div className="space-y-6">
      {/* App Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-zinc-900/60 border border-zinc-800/80 rounded-2xl p-5 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-purple-950/80 border border-purple-800/80 text-purple-300 flex items-center justify-center shadow-md">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
            </svg>
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold tracking-tight text-white">WorkFlow Mail</h1>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-purple-950/60 text-purple-300 border border-purple-800/60">
                Demo Email Application
              </span>
            </div>
            <p className="text-xs text-zinc-400 mt-0.5">
              Simulated enterprise webmail client for Playwright automation
            </p>
          </div>
        </div>

        {/* Workflow Action Helper Pill */}
        <div className="flex items-center gap-2">
          <div className="text-right hidden sm:block">
            <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-500 block">Current Automation Step</span>
            <span className="text-xs font-mono font-medium text-cyan-300">
              open_email → download_attachment
            </span>
          </div>
          <div className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-pulse hidden sm:block" />
        </div>
      </div>

      {/* Main Mail Container (Sidebar + Content View) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 min-h-[550px]">
        {/* Sidebar Folders */}
        <aside className="lg:col-span-3 space-y-4">
          <div className="bg-zinc-900/50 border border-zinc-800/80 rounded-xl p-3 space-y-1">
            <button
              onClick={() => setSelectedEmailId(null)}
              className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium transition cursor-pointer ${
                selectedEmailId === null
                  ? "bg-purple-950/60 text-purple-200 border border-purple-800/60"
                  : "text-zinc-300 hover:bg-zinc-800/60"
              }`}
            >
              <div className="flex items-center gap-2.5">
                <svg className="w-4 h-4 text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
                </svg>
                <span>Inbox</span>
              </div>
              <span className="px-1.5 py-0.2 rounded font-mono text-[10px] bg-purple-900/80 text-purple-200">
                {emails.filter((e) => e.isUnread).length}
              </span>
            </button>

            <div className="flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium text-zinc-500 hover:text-zinc-400 transition cursor-not-allowed">
              <div className="flex items-center gap-2.5">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                </svg>
                <span>Sent Messages</span>
              </div>
              <span className="text-[10px] font-mono">14</span>
            </div>

            <div className="flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium text-zinc-500 hover:text-zinc-400 transition cursor-not-allowed">
              <div className="flex items-center gap-2.5">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                <span>Drafts</span>
              </div>
              <span className="text-[10px] font-mono">2</span>
            </div>
          </div>

          {/* Quick automation guidance card */}
          <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-3.5 text-xs font-sans space-y-2">
            <span className="text-[10px] font-mono uppercase tracking-wider text-purple-400 font-semibold block">
              Playwright Target
            </span>
            <p className="text-zinc-400 text-[11px] leading-relaxed">
              Locate email from <strong className="text-white">Rahul</strong>, trigger{" "}
              <code className="text-cyan-300 bg-zinc-900 px-1 py-0.5 rounded font-mono">data-testid=&quot;open-email&quot;</code>,
              then download attachment with{" "}
              <code className="text-cyan-300 bg-zinc-900 px-1 py-0.5 rounded font-mono">data-testid=&quot;download-attachment&quot;</code>.
            </p>
          </div>
        </aside>

        {/* Content Panel: Either Email List or Email Viewer */}
        <section className="lg:col-span-9 bg-zinc-900/50 border border-zinc-800/80 rounded-xl overflow-hidden shadow-sm flex flex-col">
          {!selectedEmail ? (
            /* 1. Email Inbox List View */
            <div className="flex-1 flex flex-col">
              <div className="px-5 py-3.5 border-b border-zinc-800/80 bg-zinc-900/30 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <h2 className="text-sm font-semibold text-white">Inbox</h2>
                  <span className="text-xs text-zinc-500 font-mono">({emails.length} conversations)</span>
                </div>
                <span className="text-[11px] text-zinc-500 font-mono">Sorted by newest</span>
              </div>

              <div className="divide-y divide-zinc-800/60 overflow-y-auto">
                {emails.map((email) => (
                  <div
                    key={email.id}
                    data-testid="email-item"
                    id={`email-row-${email.id}`}
                    onClick={() => handleOpenEmail(email.id)}
                    className={`p-4 hover:bg-zinc-800/40 transition group cursor-pointer flex flex-col sm:flex-row sm:items-center justify-between gap-3 ${
                      email.isUnread ? "bg-zinc-900/40" : "bg-transparent"
                    }`}
                  >
                    <div className="flex items-start sm:items-center gap-3 min-w-0">
                      {/* Unread dot */}
                      <span
                        className={`w-2 h-2 rounded-full shrink-0 mt-1 sm:mt-0 ${
                          email.isUnread ? "bg-cyan-400" : "bg-transparent"
                        }`}
                      />

                      {/* Sender Avatar */}
                      <div className="w-8 h-8 rounded-full bg-gradient-to-br from-purple-800 to-indigo-900 text-purple-200 font-bold font-mono text-xs flex items-center justify-center shrink-0">
                        {email.senderName.charAt(0)}
                      </div>

                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className={`text-xs ${email.isUnread ? "font-bold text-white" : "font-medium text-zinc-300"}`}>
                            {email.senderName}
                          </span>
                          <span className="text-[11px] text-zinc-500 font-mono truncate">
                            &lt;{email.senderEmail}&gt;
                          </span>
                        </div>
                        <p className={`text-xs truncate ${email.isUnread ? "font-semibold text-zinc-100" : "text-zinc-300"}`}>
                          {email.subject}
                        </p>
                        <p className="text-[11px] text-zinc-500 truncate max-w-xl">
                          {email.preview}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-3 shrink-0 self-end sm:self-center pl-7 sm:pl-0">
                      {email.hasAttachment && (
                        <span
                          data-testid="attachment"
                          className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono bg-purple-950/60 text-purple-300 border border-purple-800/60"
                          title="Contains PDF attachment"
                        >
                          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
                          </svg>
                          PDF
                        </span>
                      )}

                      <span className="text-[11px] text-zinc-500 font-mono">
                        {email.timestamp}
                      </span>

                      {/* Explicit Open Button for Automation */}
                      <button
                        data-testid="open-email"
                        id={`open-email-${email.id}`}
                        onClick={(e) => {
                          e.stopPropagation();
                          handleOpenEmail(email.id);
                        }}
                        className="px-2.5 py-1 text-xs font-medium rounded-lg bg-zinc-800 hover:bg-indigo-600 text-zinc-300 hover:text-white transition active:scale-95 cursor-pointer"
                      >
                        Open
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            /* 2. Email Detail Viewer */
            <div className="flex-1 flex flex-col" id="email-detail-view">
              {/* Back to Inbox Bar */}
              <div className="px-5 py-3 border-b border-zinc-800/80 bg-zinc-900/30 flex items-center justify-between">
                <button
                  onClick={() => setSelectedEmailId(null)}
                  className="flex items-center gap-1.5 text-xs text-zinc-400 hover:text-white font-medium transition cursor-pointer"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                  </svg>
                  <span>Back to Inbox</span>
                </button>

                <div className="flex items-center gap-2">
                  <span className="text-[11px] text-zinc-500 font-mono">
                    ID: {selectedEmail.id}
                  </span>
                </div>
              </div>

              {/* Email Content Header */}
              <div className="p-6 border-b border-zinc-800/60 space-y-4">
                <h2 className="text-xl font-bold text-white tracking-tight">
                  {selectedEmail.subject}
                </h2>

                <div className="flex items-center justify-between gap-4 flex-wrap">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-gradient-to-br from-purple-700 via-indigo-700 to-cyan-700 text-white font-bold font-mono text-sm flex items-center justify-center">
                      {selectedEmail.senderName.charAt(0)}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-semibold text-white">
                          {selectedEmail.senderName}
                        </span>
                        <span className="text-xs text-zinc-400 font-mono">
                          &lt;{selectedEmail.senderEmail}&gt;
                        </span>
                      </div>
                      <p className="text-[11px] text-zinc-500">
                        to <span className="text-zinc-400">support@workflowos.io</span>
                      </p>
                    </div>
                  </div>

                  <span className="text-xs font-mono text-zinc-500">
                    {selectedEmail.timestamp}
                  </span>
                </div>
              </div>

              {/* Email Body */}
              <div className="p-6 flex-1 text-sm text-zinc-200 leading-relaxed font-sans whitespace-pre-line">
                {selectedEmail.body}
              </div>

              {/* Attachment Section */}
              {selectedEmail.hasAttachment && selectedEmail.attachmentName && (
                <div
                  data-testid="attachment"
                  id="email-attachment-container"
                  className="p-5 border-t border-zinc-800/80 bg-zinc-950/70 space-y-3"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <svg className="w-4 h-4 text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
                      </svg>
                      <span className="text-xs font-semibold text-white">Attachments (1 file)</span>
                    </div>

                    {/* Download Confirmation Badge */}
                    {downloadedAttachments[selectedEmail.attachmentName] && (
                      <span
                        data-testid="download-status"
                        className="inline-flex items-center gap-1.5 text-xs font-semibold text-emerald-300 bg-emerald-950/60 border border-emerald-800/80 px-2.5 py-0.5 rounded-full animate-fadeIn"
                      >
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
                        Attachment downloaded ✓
                      </span>
                    )}
                  </div>

                  {/* Attachment Card */}
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3.5 rounded-xl bg-zinc-900 border border-zinc-800">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-lg bg-rose-950/60 border border-rose-800/60 text-rose-300 flex items-center justify-center font-mono font-bold text-xs">
                        PDF
                      </div>
                      <div>
                        <p className="text-xs font-medium text-white font-mono">
                          {selectedEmail.attachmentName}
                        </p>
                        <p className="text-[11px] text-zinc-500 font-mono">
                          {selectedEmail.attachmentSize} • Document / Application
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      {downloadedAttachments[selectedEmail.attachmentName] ? (
                        <button
                          onClick={() => handleResetAttachment(selectedEmail.attachmentName!)}
                          className="px-2.5 py-1 text-[11px] text-zinc-500 hover:text-zinc-300 underline font-mono cursor-pointer"
                        >
                          Reset
                        </button>
                      ) : null}

                      <button
                        data-testid="download-attachment"
                        id="download-attachment-btn"
                        onClick={() => handleDownloadAttachment(selectedEmail.attachmentName!)}
                        className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-semibold transition active:scale-95 cursor-pointer ${
                          downloadedAttachments[selectedEmail.attachmentName]
                            ? "bg-emerald-950 text-emerald-200 border border-emerald-800/80 hover:bg-emerald-900/60"
                            : "bg-indigo-600 hover:bg-indigo-500 text-white shadow-md shadow-indigo-950"
                        }`}
                      >
                        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                        </svg>
                        <span>
                          {downloadedAttachments[selectedEmail.attachmentName]
                            ? "Download Again"
                            : "Download Attachment"}
                        </span>
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
