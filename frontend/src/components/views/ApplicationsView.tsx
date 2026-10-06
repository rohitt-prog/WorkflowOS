"use client";

import React, { useState, useEffect, useCallback } from "react";
import { API_BASE_URL, formatApiErrorMessage } from "@/lib/utils";
import { ApplicationSummary, ApplicationCapability } from "@/lib/types";

export default function ApplicationsView() {
  const [applications, setApplications] = useState<ApplicationSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedAppId, setSelectedAppId] = useState<string | null>(null);

  const fetchApplications = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/applications`, { cache: "no-store" });
      if (!res.ok) {
        throw new Error(`Failed to load applications: HTTP ${res.status}`);
      }
      const data: ApplicationSummary[] = await res.json();
      setApplications(data);
      setSelectedAppId((prev) => (prev ? prev : (data.length > 0 ? data[0].application_id : null)));
      setError(null);
    } catch (err) {
      setError(formatApiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  const handleManualRefresh = () => {
    setLoading(true);
    fetchApplications();
  };

  useEffect(() => {
    let isMounted = true;
    const load = async () => {
      if (!isMounted) return;
      await fetchApplications();
    };
    load();
    return () => {
      isMounted = false;
    };
  }, [fetchApplications]);

  const getStatusBadge = (app: ApplicationSummary) => {
    const status = (app.connection_status || app.health?.status || "UNKNOWN").toUpperCase();

    if (app.is_demo) {
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-purple-50 text-purple-700 border border-purple-200">
          Demo App
        </span>
      );
    }

    if (status === "CONNECTED" || app.health?.connected) {
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
          ● Connected
        </span>
      );
    }

    if (status === "AVAILABLE") {
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-50 text-blue-700 border border-blue-200">
          Available
        </span>
      );
    }

    if (status === "DEGRADED") {
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200">
          Degraded
        </span>
      );
    }

    if (status === "NOT_CONFIGURED") {
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-50 text-slate-600 border border-slate-200">
          Not Configured
        </span>
      );
    }

    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-rose-50 text-rose-700 border border-rose-200">
        Unavailable
      </span>
    );
  };

  const selectedApp = applications.find((a) => a.application_id === selectedAppId) || applications[0];

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Header bar */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-[#0F172A] tracking-tight">Application Ecosystem</h2>
          <p className="text-sm text-[#64748B] mt-0.5">
            Registered ecosystem applications, connection health, and capability safety classifications.
          </p>
        </div>
        <button
          onClick={handleManualRefresh}
          disabled={loading}
          className="px-3.5 py-1.5 text-xs font-medium rounded-md bg-white border border-[#CBD5E1] text-[#334155] hover:bg-[#F8FAFC] disabled:opacity-50 transition-colors shadow-2xs"
        >
          {loading ? "Refreshing..." : "Refresh Status"}
        </button>
      </div>

      {error && (
        <div className="p-4 rounded-md bg-rose-50 border border-rose-200 text-rose-800 text-sm">
          {error}
        </div>
      )}

      {loading && applications.length === 0 ? (
        <div className="p-12 text-center text-sm text-[#64748B] bg-white rounded-lg border border-[#E2E8F0]">
          Loading registered applications...
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Applications List */}
          <div className="space-y-3">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-[#94A3B8] px-1">
              Applications ({applications.length})
            </h3>
            {applications.map((app) => {
              const isSelected = app.application_id === (selectedApp?.application_id);
              return (
                <div
                  key={app.application_id}
                  onClick={() => setSelectedAppId(app.application_id)}
                  className={`p-4 rounded-lg border cursor-pointer transition-all ${
                    isSelected
                      ? "bg-white border-[#2563EB] shadow-xs ring-1 ring-[#2563EB]/20"
                      : "bg-white border-[#E2E8F0] hover:border-[#CBD5E1]"
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <h4 className="text-sm font-semibold text-[#0F172A] truncate">
                        {app.display_name}
                      </h4>
                      <p className="text-xs text-[#64748B] font-mono mt-0.5">
                        {app.application_id}
                      </p>
                    </div>
                    <div>{getStatusBadge(app)}</div>
                  </div>

                  <p className="text-xs text-[#475569] mt-2 line-clamp-2">
                    {app.description || `${app.capabilities.length} capabilities exposed`}
                  </p>

                  <div className="mt-3 pt-2.5 border-t border-[#F1F5F9] flex items-center justify-between text-[11px] text-[#64748B]">
                    <span>{app.capabilities.length} actions</span>
                    <span className="capitalize">{app.integration_type} integration</span>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Details / Capabilities panel */}
          <div className="lg:col-span-2">
            {selectedApp ? (
              <div className="bg-white rounded-lg border border-[#E2E8F0] p-6 space-y-6">
                {/* Detail Header */}
                <div className="flex items-start justify-between gap-4 pb-4 border-b border-[#E2E8F0]">
                  <div>
                    <div className="flex items-center gap-2.5">
                      <h3 className="text-lg font-bold text-[#0F172A]">
                        {selectedApp.display_name}
                      </h3>
                      {getStatusBadge(selectedApp)}
                    </div>
                    <p className="text-xs text-[#64748B] font-mono mt-1">
                      ID: {selectedApp.application_id} • Type: {selectedApp.integration_type}
                    </p>
                    {selectedApp.description && (
                      <p className="text-sm text-[#334155] mt-2">
                        {selectedApp.description}
                      </p>
                    )}
                  </div>

                  <div className="text-right text-xs text-[#64748B] shrink-0">
                    <div>Health: <span className="font-semibold text-[#0F172A]">{selectedApp.health?.status || "UNKNOWN"}</span></div>
                    {selectedApp.health?.message && (
                      <div className="text-[11px] text-[#475569] mt-0.5 max-w-xs">{selectedApp.health.message}</div>
                    )}
                  </div>
                </div>

                {/* Authentication Requirements */}
                {selectedApp.auth_requirements && selectedApp.auth_requirements.length > 0 && (
                  <div className="p-3 rounded-md bg-[#F8FAFC] border border-[#E2E8F0]">
                    <div className="text-xs font-semibold text-[#475569] uppercase tracking-wider mb-1">
                      Authentication Requirements
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {selectedApp.auth_requirements.map((req, i) => (
                        <span
                          key={i}
                          className="px-2 py-0.5 rounded text-xs font-mono bg-white border border-[#CBD5E1] text-[#334155]"
                        >
                          {req}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Capabilities List */}
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <h4 className="text-xs font-semibold uppercase tracking-wider text-[#94A3B8]">
                      Exposed Capabilities ({selectedApp.capabilities.length})
                    </h4>
                    <span className="text-xs text-[#64748B]">
                      Mutating actions require explicit approval
                    </span>
                  </div>

                  {selectedApp.capabilities.length === 0 ? (
                    <div className="p-6 text-center text-xs text-[#64748B] bg-[#F8FAFC] rounded-md border border-[#E2E8F0]">
                      No actions exposed for this application.
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {selectedApp.capabilities.map((cap: ApplicationCapability) => (
                        <div
                          key={cap.action_id}
                          className="p-3.5 rounded-md border border-[#E2E8F0] bg-[#FAFAFA] hover:bg-white transition-colors"
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div>
                              <div className="flex items-center gap-2">
                                <span className="text-sm font-semibold text-[#0F172A]">
                                  {cap.display_name || cap.action_id}
                                </span>
                                <span className="text-xs font-mono text-[#64748B]">
                                  ({cap.action_id})
                                </span>
                              </div>
                              <p className="text-xs text-[#475569] mt-1">
                                {cap.description}
                              </p>
                            </div>

                            <div className="flex items-center gap-1.5 shrink-0">
                              {cap.read_only ? (
                                <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
                                  Read-only
                                </span>
                              ) : (
                                <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-amber-50 text-amber-700 border border-amber-200">
                                  Mutating
                                </span>
                              )}

                              {cap.requires_approval && (
                                <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-rose-50 text-rose-700 border border-rose-200" title="Approval Gate Required">
                                  Approval Required
                                </span>
                              )}
                            </div>
                          </div>

                          {/* Strategies supported */}
                          {cap.supported_strategies && cap.supported_strategies.length > 0 && (
                            <div className="mt-2.5 pt-2 border-t border-[#E2E8F0] flex items-center gap-2 text-[11px] text-[#64748B]">
                              <span className="font-medium text-[#475569]">Strategies:</span>
                              <div className="flex gap-1">
                                {cap.supported_strategies.map((st) => (
                                  <span
                                    key={st}
                                    className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-white border border-[#CBD5E1] text-[#334155]"
                                  >
                                    {st}
                                  </span>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="p-12 text-center text-sm text-[#64748B] bg-white rounded-lg border border-[#E2E8F0]">
                Select an application to view details.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
