"use client";

import React, { useState, useEffect, useCallback } from "react";
import { API_BASE_URL } from "@/lib/utils";
import { IntegrationSummaryItem } from "@/lib/types";

export default function SettingsView() {
  const [copiedCmd, setCopiedCmd] = useState<string | null>(null);

  // Phase 7.1: Integrations State
  const [integrations, setIntegrations] = useState<IntegrationSummaryItem[]>([]);
  const [integrationsLoading, setIntegrationsLoading] = useState(true);
  const [actionLoadingId, setActionLoadingId] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<{
    integrationId: string;
    message: string;
    success: boolean;
  } | null>(null);

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedCmd(text);
    setTimeout(() => setCopiedCmd(null), 2000);
  };

  const fetchIntegrations = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/integrations`, { cache: "no-store" });
      if (res.ok) {
        const data: IntegrationSummaryItem[] = await res.json();
        setIntegrations(data);
      }
    } catch {
      // Backend may be offline during initial boot
    } finally {
      setIntegrationsLoading(false);
    }
  }, []);

  useEffect(() => {
    let isMounted = true;
    const load = async () => {
      if (!isMounted) return;
      await fetchIntegrations();
    };
    load();
    return () => {
      isMounted = false;
    };
  }, [fetchIntegrations]);

  const handleConnect = async (id: string) => {
    setActionLoadingId(`connect_${id}`);
    setActionNotice(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/integrations/${id}/connect`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ credentials: {} }),
      });
      if (res.ok) {
        setActionNotice({
          integrationId: id,
          message: "Integration connected successfully.",
          success: true,
        });
        await fetchIntegrations();
      } else {
        const err = await res.json();
        setActionNotice({
          integrationId: id,
          message: err.detail || "Failed to connect integration.",
          success: false,
        });
      }
    } catch {
      setActionNotice({
        integrationId: id,
        message: "Network error connecting integration.",
        success: false,
      });
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleDisconnect = async (id: string) => {
    setActionLoadingId(`disconnect_${id}`);
    setActionNotice(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/integrations/${id}/disconnect`, {
        method: "POST",
      });
      if (res.ok) {
        setActionNotice({
          integrationId: id,
          message: "Integration disconnected.",
          success: true,
        });
        await fetchIntegrations();
      } else {
        const err = await res.json();
        setActionNotice({
          integrationId: id,
          message: err.detail || "Failed to disconnect.",
          success: false,
        });
      }
    } catch {
      setActionNotice({
        integrationId: id,
        message: "Network error disconnecting integration.",
        success: false,
      });
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleTestAction = async (id: string, actionName: string) => {
    setActionLoadingId(`test_${id}`);
    setActionNotice(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/integrations/${id}/actions/${actionName}/execute`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          parameters: { message: "Test payload from WorkFlowOS Settings" },
        }),
      });
      const data = await res.json();
      if (res.ok && data.success) {
        setActionNotice({
          integrationId: id,
          message: `Executed '${actionName}': ${data.data?.echoed_message || data.message}`,
          success: true,
        });
      } else {
        setActionNotice({
          integrationId: id,
          message: data.detail || data.message || "Action execution failed.",
          success: false,
        });
      }
    } catch {
      setActionNotice({
        integrationId: id,
        message: "Network error executing test action.",
        success: false,
      });
    } finally {
      setActionLoadingId(null);
    }
  };

  return (
    <div className="p-6 space-y-6 max-w-3xl mx-auto bg-[#F7F9FC]">
      {/* View Header */}
      <div className="bg-white border border-[#E2E8F0] rounded-xl p-5 shadow-2xs">
        <h2 className="text-base font-bold text-[#0F172A] tracking-tight">
          System Preferences & Configuration
        </h2>
        <p className="text-xs text-[#64748B] mt-0.5">
          Backend API configuration, service integration adapters, and phase readiness checklist.
        </p>
      </div>

      {/* API Endpoint Section */}
      <section className="bg-white border border-[#E2E8F0] rounded-xl p-5 space-y-4 shadow-2xs">
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-[#64748B]">
            Backend Connection
          </h3>
          <p className="text-xs text-[#475569] mt-0.5">
            Active REST API endpoint targeted by the WorkFlowOS frontend.
          </p>
        </div>

        <div>
          <label className="text-xs font-semibold text-[#0F172A] block mb-1">
            API Base URL
          </label>
          <div className="flex items-center gap-2">
            <input
              type="text"
              readOnly
              value={API_BASE_URL}
              className="flex-1 bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg px-3 py-2 text-xs text-[#0F172A] font-mono focus:outline-none cursor-default select-all"
            />
            <span className="text-[11px] font-mono text-[#94A3B8] px-2 py-1 rounded bg-[#F1F5F9] border border-[#E2E8F0]">
              NEXT_PUBLIC_API_URL
            </span>
          </div>
          <p className="text-[11px] text-[#64748B] mt-1.5">
            Configured locally via <code className="text-[#0F172A] font-mono bg-[#F1F5F9] px-1 py-0.5 rounded">.env.local</code>.
          </p>
        </div>
      </section>

      {/* Phase 7.1: Service Integrations & Adapters Section */}
      <section className="bg-white border border-[#E2E8F0] rounded-xl p-5 space-y-4 shadow-2xs">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-[#64748B]">
              Service Integrations & Adapters
            </h3>
            <p className="text-xs text-[#475569] mt-0.5">
              Central adapter registry, connection lifecycles, and capability declarations (Phase 7.1).
            </p>
          </div>
          <button
            onClick={fetchIntegrations}
            className="text-[11px] text-[#2563EB] hover:text-[#1D4ED8] font-medium cursor-pointer"
          >
            Refresh
          </button>
        </div>

        {integrationsLoading ? (
          <div className="py-6 text-center text-xs text-[#94A3B8]">
            Loading registered integrations...
          </div>
        ) : integrations.length === 0 ? (
          <div className="py-6 text-center text-xs text-[#94A3B8] border border-dashed border-[#E2E8F0] rounded-xl">
            No integration adapters discovered. Ensure the backend is running.
          </div>
        ) : (
          <div className="space-y-4">
            {integrations.map((item) => {
              const isConnecting = actionLoadingId === `connect_${item.id}`;
              const isDisconnecting = actionLoadingId === `disconnect_${item.id}`;
              const isTesting = actionLoadingId === `test_${item.id}`;
              const notice = actionNotice && actionNotice.integrationId === item.id ? actionNotice : null;

              return (
                <div
                  key={item.id}
                  className="border border-[#E2E8F0] rounded-xl p-4.5 bg-white space-y-3.5 hover:border-[#CBD5E1] transition shadow-2xs"
                >
                  {/* Adapter Header */}
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-center gap-2.5">
                      <div className="w-8 h-8 rounded-lg bg-[#EFF6FF] border border-[#BFDBFE] flex items-center justify-center text-[#2563EB] shrink-0 font-mono text-xs font-bold">
                        {item.icon === "flask" ? "⚗" : "🔌"}
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <h4 className="text-xs font-bold text-[#0F172A]">
                            {item.name}
                          </h4>
                          <span className="text-[10px] font-mono text-[#64748B] bg-[#F1F5F9] px-1.5 py-0.5 rounded border border-[#E2E8F0]">
                            v{item.version}
                          </span>
                          {item.is_mock && (
                            <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200">
                              Mock / Non-Production
                            </span>
                          )}
                        </div>
                        <p className="text-[11px] text-[#64748B] mt-0.5">
                          Identifier: <code className="font-mono text-[#0F172A]">{item.id}</code>
                        </p>
                      </div>
                    </div>

                    {/* Status Pill */}
                    <div className="shrink-0">
                      {item.is_connected ? (
                        <span className="inline-flex items-center gap-1.5 text-[11px] font-medium px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                          Connected
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 text-[11px] font-medium px-2.5 py-1 rounded-full bg-slate-50 text-slate-600 border border-slate-200">
                          <span className="w-1.5 h-1.5 rounded-full bg-slate-400" />
                          Disconnected
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Description */}
                  <p className="text-xs text-[#475569] leading-relaxed">
                    {item.description}
                  </p>

                  {/* Mock Disclaimer Alert */}
                  {item.disclaimer && (
                    <div className="bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg p-2.5 flex items-start gap-2 text-[11px] text-[#64748B]">
                      <span className="text-amber-500 text-xs shrink-0 mt-0.5">⚠️</span>
                      <span className="leading-tight">{item.disclaimer}</span>
                    </div>
                  )}

                  {/* Declared Actions list */}
                  {item.actions && item.actions.length > 0 && (
                    <div className="space-y-1.5 pt-1 border-t border-[#F1F5F9]">
                      <span className="text-[10px] font-semibold uppercase tracking-wider text-[#94A3B8]">
                        Declared Capabilities ({item.actions.length})
                      </span>
                      <div className="flex flex-wrap gap-1.5">
                        {item.actions.map((act) => (
                          <div
                            key={act.name}
                            className="inline-flex items-center gap-1.5 px-2 py-1 rounded bg-[#F8FAFC] border border-[#E2E8F0] text-[11px]"
                          >
                            <span className="font-mono text-[#0F172A] font-medium">{act.name}</span>
                            <span className="text-[#94A3B8]">•</span>
                            <span className="text-[#64748B] text-[10px]">{act.display_name}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Action Notification Alert */}
                  {notice && (
                    <div
                      className={`text-xs px-3 py-2 rounded-lg border ${
                        notice.success
                          ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                          : "bg-red-50 text-red-800 border-red-200"
                      }`}
                    >
                      {notice.message}
                    </div>
                  )}

                  {/* Controls */}
                  <div className="flex items-center gap-2 pt-2 border-t border-[#F1F5F9]">
                    {!item.is_connected ? (
                      <button
                        onClick={() => handleConnect(item.id)}
                        disabled={isConnecting}
                        className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-[#2563EB] text-white hover:bg-[#1D4ED8] transition shadow-2xs cursor-pointer disabled:opacity-50"
                      >
                        {isConnecting ? "Connecting..." : "Connect Adapter"}
                      </button>
                    ) : (
                      <>
                        <button
                          onClick={() => handleDisconnect(item.id)}
                          disabled={isDisconnecting}
                          className="px-3 py-1.5 text-xs font-medium rounded-lg border border-[#E2E8F0] text-[#64748B] hover:bg-[#FEE2E2] hover:text-[#DC2626] hover:border-[#FECACA] transition cursor-pointer disabled:opacity-50"
                        >
                          {isDisconnecting ? "Disconnecting..." : "Disconnect"}
                        </button>

                        <button
                          onClick={() => handleTestAction(item.id, "mock_echo")}
                          disabled={isTesting}
                          className="px-3 py-1.5 text-xs font-medium rounded-lg bg-[#EFF6FF] border border-[#BFDBFE] text-[#1D4ED8] hover:bg-[#DBEAFE] transition cursor-pointer disabled:opacity-50"
                        >
                          {isTesting ? "Executing..." : "Test mock_echo Action"}
                        </button>
                      </>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* Phase Info Status */}
      <section className="bg-white border border-[#E2E8F0] rounded-xl p-5 space-y-4 shadow-2xs">
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-[#64748B]">
            Platform Milestones & Architecture
          </h3>
          <p className="text-xs text-[#475569] mt-0.5">
            Architectural layers completed and verified in the current WorkFlowOS build.
          </p>
        </div>

        <div className="divide-y divide-[#E2E8F0] border border-[#E2E8F0] rounded-xl overflow-hidden">
          {[
            { phase: "Phase 1", label: "Observational Event Ingestion & MongoDB Atlas", status: "complete" },
            { phase: "Phase 2", label: "Algorithmic Workflow Discovery (Repetition Scanner)", status: "complete" },
            { phase: "Phase 3", label: "AI Workflow Understanding & Gemini SDK Proposal Engine", status: "complete" },
            { phase: "Phase 4", label: "Playwright Automation Execution + Human Approval Gate", status: "complete" },
            { phase: "Phase 5", label: "Real macOS Desktop Activity Agent (NSWorkspace Native)", status: "complete" },
            { phase: "Phase 6", label: "Declarative Workflow Engine & Modern Light UI Redesign", status: "complete" },
            { phase: "Phase 7.1", label: "Integration Foundation (Registry, Adapter Abstraction & Mock Adapter)", status: "complete" },
          ].map(({ phase, label }) => (
            <div key={phase} className="flex items-center justify-between p-3 text-xs bg-white hover:bg-[#F8FAFC] transition">
              <div className="flex items-center gap-3">
                <span className="w-2 h-2 rounded-full bg-[#16A34A] shrink-0" />
                <span className="font-mono font-bold text-[#0F172A] w-24 shrink-0">{phase}</span>
                <span className="text-[#475569]">{label}</span>
              </div>
              <span className="text-[10px] font-semibold uppercase px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 shrink-0">
                Verified
              </span>
            </div>
          ))}
        </div>
      </section>

      {/* Useful Commands Section */}
      <section className="bg-white border border-[#E2E8F0] rounded-xl p-5 space-y-4 shadow-2xs">
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-[#64748B]">
            Operational CLI Commands
          </h3>
          <p className="text-xs text-[#475569] mt-0.5">
            Standard development and agent control commands.
          </p>
        </div>

        <div className="space-y-2.5">
          {[
            { label: "Start macOS Activity Agent", cmd: "python -m agent run" },
            { label: "Inspect Desktop Agent Status", cmd: "python -m agent status" },
            { label: "Run All Test Suites (Phases 1–7.1)", cmd: ".venv/bin/python3 -m unittest discover -s backend -p 'test_phase*.py'" },
            { label: "Start FastAPI Backend", cmd: "uvicorn backend.main:app --reload --port 8000" },
          ].map(({ label, cmd }) => (
            <div key={cmd} className="space-y-1">
              <span className="text-[11px] font-medium text-[#64748B] block">{label}</span>
              <div className="flex items-center gap-2">
                <code className="flex-1 text-xs font-mono text-[#0F172A] bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg px-3 py-2 select-all">
                  {cmd}
                </code>
                <button
                  onClick={() => copyToClipboard(cmd)}
                  className="px-2.5 py-2 text-xs font-medium rounded-lg bg-white border border-[#E2E8F0] text-[#0F172A] hover:bg-[#F8FAFC] shadow-2xs transition cursor-pointer shrink-0"
                >
                  {copiedCmd === cmd ? "Copied!" : "Copy"}
                </button>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Privacy Guarantee Card */}
      <section className="bg-white border border-[#E2E8F0] rounded-xl p-5 shadow-2xs space-y-2">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-[#64748B]">
          Privacy & Local Security Guarantee
        </h3>
        <p className="text-xs text-[#475569] leading-relaxed">
          The Phase 5 desktop agent uses Apple macOS native NSWorkspace APIs strictly for application activation tracking.
          It never captures keystrokes, passwords, clipboard data, or screen pixels. All captured telemetry remains in your
          local MongoDB Atlas cluster and is executed locally via Playwright with explicit operator approval.
          Phase 7.1 enforces strict credential redaction and rejects plaintext OAuth token storage.
        </p>
      </section>
    </div>
  );
}
