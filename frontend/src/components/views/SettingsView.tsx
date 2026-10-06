"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  API_BASE_URL,
} from "@/lib/utils";
import {
  IntegrationSummaryItem,
  SystemSettingsResponse,
  PrivacyStatusResponse,
} from "@/lib/types";
import {
  fetchSystemSettings,
  fetchPrivacyStatus,
  togglePrivacyCollection,
  triggerRetentionCleanup,
  auditPrivacyPayload,
  fetchIntegrations,
  connectIntegration,
  disconnectIntegration,
  testIntegrationAction,
} from "@/lib/api";

interface GmailMessagePreview {
  id: string;
  thread_id?: string;
  from?: string;
  subject?: string;
  date?: string;
  snippet?: string;
}

export default function SettingsView() {
  const [copiedCmd, setCopiedCmd] = useState<string | null>(null);

  // System Settings & Privacy States
  const [sysSettings, setSysSettings] = useState<SystemSettingsResponse | null>(null);
  const [privacyStatus, setPrivacyStatus] = useState<PrivacyStatusResponse | null>(null);
  const [settingsLoading, setSettingsLoading] = useState(true);
  const [togglingPrivacy, setTogglingPrivacy] = useState(false);
  const [privacyMessage, setPrivacyMessage] = useState<string | null>(null);

  // Retention cleanup state
  const [retentionRunning, setRetentionRunning] = useState(false);
  const [retentionReport, setRetentionReport] = useState<string | null>(null);

  // Interactive Redaction Auditor state
  const [auditInput, setAuditInput] = useState('{\n  "username": "alex",\n  "api_key": "sk-1234567890",\n  "password": "supersecretpassword"\n}');
  const [auditResult, setAuditResult] = useState<{
    contains_sensitive_data: boolean;
    detected_categories: string[];
    redacted_fields: string[];
  } | null>(null);
  const [auditLoading, setAuditLoading] = useState(false);

  // Integrations State
  const [integrations, setIntegrations] = useState<IntegrationSummaryItem[]>([]);
  const [integrationsLoading, setIntegrationsLoading] = useState(true);
  const [actionLoadingId, setActionLoadingId] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<{
    integrationId: string;
    message: string;
    success: boolean;
    data?: { messages?: GmailMessagePreview[]; count?: number; echoed_message?: string };
  } | null>(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      const statusParam = params.get("status");
      const integrationParam = params.get("integration");
      const messageParam = params.get("message");

      if (integrationParam === "gmail") {
        if (statusParam === "connected") {
          return {
            integrationId: "gmail",
            message: "Gmail successfully connected via Google OAuth 2.0.",
            success: true,
          };
        } else if (statusParam === "error") {
          return {
            integrationId: "gmail",
            message: messageParam ? decodeURIComponent(messageParam) : "Failed to connect Gmail via Google OAuth.",
            success: false,
          };
        }
      }
    }
    return null;
  });

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedCmd(text);
    setTimeout(() => setCopiedCmd(null), 2000);
  };

  const loadSettingsAndPrivacy = useCallback(async () => {
    setSettingsLoading(true);
    try {
      const [sData, pData] = await Promise.allSettled([
        fetchSystemSettings(),
        fetchPrivacyStatus(),
      ]);
      if (sData.status === "fulfilled") setSysSettings(sData.value);
      if (pData.status === "fulfilled") setPrivacyStatus(pData.value);
    } catch {
      // offline fallback
    } finally {
      setSettingsLoading(false);
    }
  }, []);

  const loadIntegrationsData = useCallback(async () => {
    setIntegrationsLoading(true);
    try {
      const data = await fetchIntegrations();
      setIntegrations(data);
    } catch {
      // offline fallback
    } finally {
      setIntegrationsLoading(false);
    }
  }, []);

  // Clean URL search query if redirected from OAuth callback
  useEffect(() => {
    if (typeof window !== "undefined" && window.location.search.includes("integration=gmail")) {
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  }, []);

  useEffect(() => {
    let isMounted = true;
    const load = async () => {
      if (!isMounted) return;
      await Promise.all([loadSettingsAndPrivacy(), loadIntegrationsData()]);
    };
    load();
    return () => {
      isMounted = false;
    };
  }, [loadSettingsAndPrivacy, loadIntegrationsData]);

  const handleToggleCollection = async () => {
    if (!privacyStatus) return;
    const targetState = !privacyStatus.collection_enabled;
    setTogglingPrivacy(true);
    setPrivacyMessage(null);
    try {
      const res = await togglePrivacyCollection(targetState);
      setPrivacyStatus((prev) =>
        prev ? { ...prev, collection_enabled: res.collection_enabled } : null
      );
      setPrivacyMessage(
        res.collection_enabled
          ? "Desktop activity collection enabled."
          : "Desktop activity collection disabled. Incoming events will be dropped at privacy gate."
      );
    } catch (e: unknown) {
      setPrivacyMessage(e instanceof Error ? e.message : "Failed to update collection state");
    } finally {
      setTogglingPrivacy(false);
    }
  };

  const handleRunRetentionCleanup = async (dryRun: boolean) => {
    setRetentionRunning(true);
    setRetentionReport(null);
    try {
      const res = await triggerRetentionCleanup(dryRun);
      if (dryRun) {
        setRetentionReport(
          `Dry-run audit: ${res.events_eligible_for_deletion} events are older than the ${res.retention_days}-day threshold (Cutoff: ${res.cutoff_timestamp.slice(0, 10)}). No records were deleted.`
        );
      } else {
        setRetentionReport(
          `Retention cleanup complete: ${res.deleted_count} expired events deleted (older than ${res.retention_days} days).`
        );
      }
    } catch (e: unknown) {
      setRetentionReport(e instanceof Error ? e.message : "Retention cleanup error");
    } finally {
      setRetentionRunning(false);
    }
  };

  const handleTestAudit = async () => {
    setAuditLoading(true);
    try {
      let parsed: unknown;
      try {
        parsed = JSON.parse(auditInput);
      } catch {
        parsed = { text: auditInput };
      }
      const res = await auditPrivacyPayload(parsed);
      setAuditResult(res);
    } catch (e: unknown) {
      setAuditResult({
        contains_sensitive_data: false,
        detected_categories: ["ERROR"],
        redacted_fields: [e instanceof Error ? e.message : "Audit error"],
      });
    } finally {
      setAuditLoading(false);
    }
  };

  const handleConnect = async (id: string) => {
    setActionLoadingId(`connect_${id}`);
    setActionNotice(null);
    try {
      await connectIntegration(id, {});
      setActionNotice({
        integrationId: id,
        message: "Integration connected successfully.",
        success: true,
      });
      await loadIntegrationsData();
    } catch (err: unknown) {
      setActionNotice({
        integrationId: id,
        message: err instanceof Error ? err.message : "Failed to connect integration.",
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
      await disconnectIntegration(id);
      setActionNotice({
        integrationId: id,
        message: "Integration disconnected.",
        success: true,
      });
      await loadIntegrationsData();
    } catch (err: unknown) {
      setActionNotice({
        integrationId: id,
        message: err instanceof Error ? err.message : "Failed to disconnect integration.",
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
      const res = (await testIntegrationAction(id, actionName, {
        message: "WorkFlowOS integration verification payload",
      })) as { success?: boolean; message?: string; data?: { echoed_message?: string } };

      setActionNotice({
        integrationId: id,
        message: res.message || "Test action completed successfully.",
        success: !!res.success,
        data: res.data,
      });
    } catch (err: unknown) {
      setActionNotice({
        integrationId: id,
        message: err instanceof Error ? err.message : "Error executing test action.",
        success: false,
      });
    } finally {
      setActionLoadingId(null);
    }
  };

  return (
    <div className="p-6 space-y-6 max-w-4xl mx-auto bg-[#F7F9FC]">
      {/* Header */}
      <div className="bg-white border border-[#E2E8F0] rounded-xl p-5 shadow-2xs flex items-center justify-between">
        <div>
          <h2 className="text-base font-bold text-[#0F172A] tracking-tight">
            Settings, Privacy & Governance
          </h2>
          <p className="text-xs text-[#64748B] mt-0.5">
            Public system configurations, privacy controls, data retention governance, and integration adapters.
          </p>
        </div>
        {settingsLoading && (
          <span className="text-[11px] font-mono text-[#94A3B8] animate-pulse">
            Loading…
          </span>
        )}
      </div>

      {/* Section 12: Privacy & Safety Controls */}
      <section className="bg-white border border-[#E2E8F0] rounded-xl p-5 space-y-4 shadow-2xs">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-[#64748B]">
              Privacy & Safety Controls (Phase 12)
            </h3>
            <p className="text-xs text-[#475569] mt-0.5">
              Strict local governance, desktop activity toggles, and recursive sensitive data scrubbing.
            </p>
          </div>
          <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200">
            Fail-Closed
          </span>
        </div>

        {privacyMessage && (
          <div className="p-3 text-xs rounded-lg bg-blue-50 border border-blue-200 text-blue-800 flex items-center justify-between">
            <span>{privacyMessage}</span>
            <button
              onClick={() => setPrivacyMessage(null)}
              className="text-blue-500 hover:text-blue-800 ml-2"
            >
              ✕
            </button>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Activity Collection Toggle */}
          <div className="border border-[#E2E8F0] rounded-xl p-4 space-y-2 bg-[#F8FAFC]">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-[#0F172A]">
                Activity Collection
              </span>
              <span
                className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${
                  privacyStatus?.collection_enabled
                    ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                    : "bg-slate-100 text-slate-600 border-slate-200"
                }`}
              >
                {privacyStatus?.collection_enabled ? "● Enabled" : "○ Disabled"}
              </span>
            </div>
            <p className="text-[11px] text-[#64748B]">
              When disabled, incoming desktop activity is rejected at the privacy gate and dropped immediately.
            </p>
            <button
              onClick={handleToggleCollection}
              disabled={togglingPrivacy}
              className={`mt-2 px-3 py-1.5 text-xs font-semibold rounded-lg transition cursor-pointer disabled:opacity-50 ${
                privacyStatus?.collection_enabled
                  ? "bg-slate-100 text-[#0F172A] hover:bg-slate-200 border border-[#E2E8F0]"
                  : "bg-[#2563EB] text-white hover:bg-[#1D4ED8]"
              }`}
            >
              {togglingPrivacy
                ? "Updating…"
                : privacyStatus?.collection_enabled
                ? "Disable Collection"
                : "Enable Collection"}
            </button>
          </div>

          {/* Event Retention Window */}
          <div className="border border-[#E2E8F0] rounded-xl p-4 space-y-2 bg-[#F8FAFC]">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-[#0F172A]">
                Event Retention Policy
              </span>
              <span className="text-xs font-mono font-bold text-[#0F172A]">
                {privacyStatus?.retention_days || 30} days
              </span>
            </div>
            <p className="text-[11px] text-[#64748B]">
              Automated expiration window. Activity events older than the threshold are eligible for purging.
            </p>
            <div className="pt-2 flex items-center gap-2">
              <button
                onClick={() => handleRunRetentionCleanup(true)}
                disabled={retentionRunning}
                className="px-3 py-1.5 text-xs font-medium rounded-lg bg-white border border-[#E2E8F0] hover:bg-[#F8FAFC] text-[#0F172A] transition cursor-pointer disabled:opacity-50"
              >
                {retentionRunning ? "Auditing…" : "Dry-Run Audit"}
              </button>
              <button
                onClick={() => {
                  if (confirm("Confirm: Purge expired events older than retention window?")) {
                    handleRunRetentionCleanup(false);
                  }
                }}
                disabled={retentionRunning}
                className="px-3 py-1.5 text-xs font-medium rounded-lg bg-rose-50 border border-rose-200 text-rose-700 hover:bg-rose-100 transition cursor-pointer disabled:opacity-50"
              >
                Purge Expired
              </button>
            </div>
          </div>
        </div>

        {retentionReport && (
          <div className="p-3 text-xs rounded-lg bg-[#F8FAFC] border border-[#E2E8F0] text-[#0F172A] font-mono">
            {retentionReport}
          </div>
        )}

        {/* Platform Guarantees Checklist */}
        <div className="border border-[#E2E8F0] rounded-xl p-4 bg-white space-y-3">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-[#64748B]">
            Enforced Platform Guarantees
          </span>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
            <div className="p-2.5 rounded bg-[#F8FAFC] border border-[#E2E8F0]">
              <span className="text-[10px] text-[#94A3B8] block">Screenshots</span>
              <span className="font-semibold text-emerald-700">Disabled (Never)</span>
            </div>
            <div className="p-2.5 rounded bg-[#F8FAFC] border border-[#E2E8F0]">
              <span className="text-[10px] text-[#94A3B8] block">Keylogging</span>
              <span className="font-semibold text-emerald-700">Disabled (Never)</span>
            </div>
            <div className="p-2.5 rounded bg-[#F8FAFC] border border-[#E2E8F0]">
              <span className="text-[10px] text-[#94A3B8] block">Computer Vision</span>
              <span className="font-semibold text-emerald-700">Disabled</span>
            </div>
            <div className="p-2.5 rounded bg-[#F8FAFC] border border-[#E2E8F0]">
              <span className="text-[10px] text-[#94A3B8] block">Mutating Actions</span>
              <span className="font-semibold text-amber-700">Approval Required</span>
            </div>
          </div>
        </div>

        {/* Live Redaction Tester */}
        <div className="border border-[#E2E8F0] rounded-xl p-4 bg-[#F8FAFC] space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-[#0F172A]">
              Test Redaction Engine (Interactive PII & Secrets Audit)
            </span>
            <span className="text-[10px] font-mono text-[#64748B]">
              Deterministic
            </span>
          </div>
          <p className="text-[11px] text-[#64748B]">
            Paste or edit JSON below to test real-time PII and credential detection:
          </p>
          <textarea
            value={auditInput}
            onChange={(e) => setAuditInput(e.target.value)}
            rows={4}
            className="w-full font-mono text-xs p-2.5 bg-white border border-[#E2E8F0] rounded-lg focus:outline-none focus:border-[#2563EB]"
          />
          <div className="flex items-center justify-between pt-1">
            <button
              onClick={handleTestAudit}
              disabled={auditLoading}
              className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-[#2563EB] text-white hover:bg-[#1D4ED8] transition cursor-pointer disabled:opacity-50"
            >
              {auditLoading ? "Auditing…" : "Audit Payload"}
            </button>
            {auditResult && (
              <span
                className={`text-xs font-semibold px-2 py-0.5 rounded-full border ${
                  auditResult.contains_sensitive_data
                    ? "bg-amber-50 text-amber-800 border-amber-200"
                    : "bg-emerald-50 text-emerald-800 border-emerald-200"
                }`}
              >
                {auditResult.contains_sensitive_data
                  ? `Sensitive Data Detected (${auditResult.redacted_fields.join(", ")})`
                  : "Clean Payload (No Secrets Detected)"}
              </span>
            )}
          </div>
        </div>
      </section>

      {/* Section 14: System Configuration & Endpoints */}
      <section className="bg-white border border-[#E2E8F0] rounded-xl p-5 space-y-4 shadow-2xs">
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-[#64748B]">
            System Endpoints & Configuration (Section 14)
          </h3>
          <p className="text-xs text-[#475569] mt-0.5">
            Public configuration values. Credential values are masked for security.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
          <div>
            <label className="text-xs font-semibold text-[#0F172A] block mb-1">
              Backend Endpoint
            </label>
            <input
              type="text"
              readOnly
              value={sysSettings?.backend_url || API_BASE_URL}
              className="w-full bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg px-3 py-2 text-xs font-mono text-[#0F172A] select-all"
            />
          </div>
          <div>
            <label className="text-xs font-semibold text-[#0F172A] block mb-1">
              Frontend Endpoint
            </label>
            <input
              type="text"
              readOnly
              value={sysSettings?.frontend_url || "http://localhost:3000"}
              className="w-full bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg px-3 py-2 text-xs font-mono text-[#0F172A] select-all"
            />
          </div>
        </div>

        {/* Masked Credentials Overview */}
        {sysSettings?.credentials_configured && (
          <div className="border border-[#E2E8F0] rounded-xl p-3.5 bg-[#F8FAFC] space-y-2">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-[#64748B]">
              Environment Secrets Status (Non-Leaking)
            </span>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {Object.entries(sysSettings.credentials_configured).map(([k, v]) => (
                <div key={k} className="p-2 rounded bg-white border border-[#E2E8F0]">
                  <span className="text-[10px] font-mono text-[#64748B] block truncate">
                    {k}
                  </span>
                  <span
                    className={`text-xs font-semibold ${
                      v === "Configured" ? "text-emerald-700" : "text-slate-500"
                    }`}
                  >
                    {v}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </section>

      {/* Service Integrations & Adapters */}
      <section className="bg-white border border-[#E2E8F0] rounded-xl p-5 space-y-4 shadow-2xs">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-[#64748B]">
              Service Integrations & Adapters
            </h3>
            <p className="text-xs text-[#475569] mt-0.5">
              External service connectivity with mandatory approval requirements.
            </p>
          </div>
          <button
            onClick={loadIntegrationsData}
            className="text-[11px] text-[#2563EB] hover:text-[#1D4ED8] font-medium cursor-pointer"
          >
            Refresh
          </button>
        </div>

        {integrationsLoading ? (
          <div className="py-6 text-center text-xs text-[#94A3B8]">
            Loading integrations…
          </div>
        ) : (
          <div className="space-y-3">
            {integrations.map((item) => {
              const isConnecting = actionLoadingId === `connect_${item.id}`;
              const isDisconnecting = actionLoadingId === `disconnect_${item.id}`;
              const isTesting = actionLoadingId === `test_${item.id}`;
              const notice = actionNotice && actionNotice.integrationId === item.id ? actionNotice : null;

              return (
                <div
                  key={item.id}
                  className="border border-[#E2E8F0] rounded-xl p-4 bg-white space-y-3"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <h4 className="text-xs font-bold text-[#0F172A]">
                          {item.name}
                        </h4>
                        <span className="text-[10px] font-mono text-[#64748B] bg-[#F1F5F9] px-1.5 py-0.5 rounded">
                          v{item.version}
                        </span>
                        {item.is_mock ? (
                          <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200">
                            Mock Adapter
                          </span>
                        ) : (
                          <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200">
                            OAuth 2.0
                          </span>
                        )}
                      </div>
                      <p className="text-[11px] text-[#64748B] mt-0.5">
                        {item.description}
                      </p>
                    </div>
                    <span
                      className={`text-[10px] font-semibold px-2.5 py-1 rounded-full border ${
                        item.is_connected
                          ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                          : "bg-slate-50 text-slate-600 border-slate-200"
                      }`}
                    >
                      {item.is_connected ? "● Connected" : "○ Disconnected"}
                    </span>
                  </div>

                  {notice && (
                    <div
                      className={`text-xs px-3 py-2 rounded-lg border ${
                        notice.success
                          ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                          : "bg-rose-50 text-rose-800 border-rose-200"
                      }`}
                    >
                      {notice.message}
                    </div>
                  )}

                  <div className="flex items-center gap-2 pt-1 border-t border-[#F1F5F9]">
                    {!item.is_connected ? (
                      item.id === "gmail" ? (
                        <a
                          href={`${API_BASE_URL}/api/integrations/gmail/connect`}
                          className="px-3 py-1.5 text-xs font-semibold rounded-lg text-white bg-[#DC2626] hover:bg-[#B91C1C] transition inline-block"
                        >
                          Connect Gmail
                        </a>
                      ) : (
                        <button
                          onClick={() => handleConnect(item.id)}
                          disabled={isConnecting}
                          className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-[#2563EB] text-white hover:bg-[#1D4ED8] transition disabled:opacity-50 cursor-pointer"
                        >
                          {isConnecting ? "Connecting…" : "Connect Adapter"}
                        </button>
                      )
                    ) : (
                      <>
                        <button
                          onClick={() => handleDisconnect(item.id)}
                          disabled={isDisconnecting}
                          className="px-3 py-1.5 text-xs font-medium rounded-lg border border-[#E2E8F0] text-[#64748B] hover:bg-rose-50 hover:text-rose-700 transition disabled:opacity-50 cursor-pointer"
                        >
                          {isDisconnecting ? "Disconnecting…" : "Disconnect"}
                        </button>
                        {item.id !== "gmail" && (
                          <button
                            onClick={() => handleTestAction(item.id, "mock_echo")}
                            disabled={isTesting}
                            className="px-3 py-1.5 text-xs font-medium rounded-lg bg-[#EFF6FF] border border-[#BFDBFE] text-[#1D4ED8] hover:bg-[#DBEAFE] transition disabled:opacity-50 cursor-pointer"
                          >
                            {isTesting ? "Executing…" : "Test mock_echo Action"}
                          </button>
                        )}
                      </>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* Operational Commands */}
      <section className="bg-white border border-[#E2E8F0] rounded-xl p-5 space-y-4 shadow-2xs">
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-[#64748B]">
            Operational CLI Commands
          </h3>
          <p className="text-xs text-[#475569] mt-0.5">
            Standard development and desktop agent management commands.
          </p>
        </div>

        <div className="space-y-2.5">
          {[
            { label: "Start macOS Desktop Activity Agent", cmd: "python -m agent run" },
            { label: "Inspect Desktop Agent Status", cmd: "python -m agent status" },
            { label: "Run Backend Unit Test Suite", cmd: ".venv/bin/python -m unittest discover -s backend -p 'test_*.py'" },
            { label: "Start FastAPI Backend Server", cmd: "uvicorn backend.main:app --reload --port 8000" },
          ].map(({ label, cmd }) => (
            <div key={cmd} className="space-y-1">
              <span className="text-[11px] font-medium text-[#64748B] block">{label}</span>
              <div className="flex items-center gap-2">
                <code className="flex-1 text-xs font-mono text-[#0F172A] bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg px-3 py-2 select-all">
                  {cmd}
                </code>
                <button
                  onClick={() => copyToClipboard(cmd)}
                  className="px-2.5 py-2 text-xs font-medium rounded-lg bg-white border border-[#E2E8F0] text-[#0F172A] hover:bg-[#F8FAFC] transition cursor-pointer shrink-0"
                >
                  {copiedCmd === cmd ? "Copied!" : "Copy"}
                </button>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
