"use client";

import React, { useState, useEffect, useCallback, useMemo } from "react";
import Link from "next/link";

// Types matching the backend EventResponse model
interface EventMetadata {
  customer?: string;
  customer_name?: string;
  client?: string;
  name?: string;
  subject?: string;
  search_query?: string;
  [key: string]: unknown;
}

interface ActivityEvent {
  id: string;
  session_id: string;
  timestamp: string;
  application: string;
  event_type: string;
  target?: string | null;
  metadata?: EventMetadata;
}

// ── Phase 2: Discovery types matching the backend DiscoveryResult model ──
interface DiscoveredWorkflow {
  label: string;
  sequence: string[];
  occurrences: number;
  similarity: number;
  session_ids: string[];
}

interface DiscoveryResult {
  detected: boolean;
  workflows: DiscoveredWorkflow[];
}

// ── Phase 3: AI Workflow Proposal types ──
interface WorkflowTrigger {
  type: string;
  application: string;
  description: string;
}

interface WorkflowAction {
  type: string;
  application: string;
  description: string;
  target: string;
}

interface WorkflowProposal {
  name: string;
  intent: string;
  trigger: WorkflowTrigger;
  actions: WorkflowAction[];
  variables: string[];
  applications: string[];
  requires_approval: boolean;
}

type ApprovalStatus = "idle" | "approved" | "rejected";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://localhost:8000";

export default function Dashboard() {
  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [backendStatus, setBackendStatus] = useState<"connected" | "disconnected" | "checking">("checking");
  const [lastRefreshed, setLastRefreshed] = useState<Date | null>(null);
  const [selectedEvent, setSelectedEvent] = useState<ActivityEvent | null>(null);
  const [searchTerm, setSearchTerm] = useState<string>("");
  const [appFilter, setAppFilter] = useState<string>("ALL");
  const [autoRefresh, setAutoRefresh] = useState<boolean>(true);
  const [mounted, setMounted] = useState<boolean>(false);

  // Phase 2: Workflow Discovery state
  const [discovery, setDiscovery] = useState<DiscoveryResult | null>(null);
  const [discoveryLoading, setDiscoveryLoading] = useState<boolean>(true);
  const [discoveryError, setDiscoveryError] = useState<string | null>(null);

  // Phase 3: AI Workflow Understanding state
  const [reviewModalOpen, setReviewModalOpen] = useState<boolean>(false);
  const [activeReviewWorkflow, setActiveReviewWorkflow] = useState<DiscoveredWorkflow | null>(null);
  const [workflowProposal, setWorkflowProposal] = useState<WorkflowProposal | null>(null);
  const [aiLoading, setAiLoading] = useState<boolean>(false);
  const [aiError, setAiError] = useState<string | null>(null);
  const [approvalStatus, setApprovalStatus] = useState<ApprovalStatus>("idle");
  const [workflowApprovals, setWorkflowApprovals] = useState<Record<string, "approved" | "rejected">>({});

  useEffect(() => {
    setMounted(true);
  }, []);

  // Fetch events & verify backend health
  const fetchData = useCallback(async (isManualRefresh = false) => {
    if (isManualRefresh) {
      setRefreshing(true);
    }
    setError(null);

    try {
      // Parallel fetch: Health check + Events list
      const [healthRes, eventsRes] = await Promise.allSettled([
        fetch(`${API_BASE_URL}/health`, { method: "GET", cache: "no-store" }),
        fetch(`${API_BASE_URL}/api/events?limit=100`, { method: "GET", cache: "no-store" }),
      ]);

      // Check health status
      if (healthRes.status === "fulfilled" && healthRes.value.ok) {
        setBackendStatus("connected");
      } else {
        setBackendStatus("disconnected");
      }

      // Check events response
      if (eventsRes.status === "fulfilled") {
        if (!eventsRes.value.ok) {
          throw new Error(`Backend returned status ${eventsRes.value.status}: ${eventsRes.value.statusText}`);
        }
        const data: ActivityEvent[] = await eventsRes.value.json();
        setEvents(data);
        setBackendStatus("connected");
      } else {
        throw new Error(eventsRes.reason?.message || "Failed to reach backend API");
      }

      setLastRefreshed(new Date());
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "An unexpected error occurred connecting to the backend.";
      setError(msg);
      setBackendStatus("disconnected");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  // Phase 2: Fetch discovery results from GET /api/discovery/repeated
  const fetchDiscovery = useCallback(async () => {
    setDiscoveryError(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/discovery/repeated`, {
        method: "GET",
        cache: "no-store",
      });
      if (!res.ok) {
        throw new Error(`Discovery API returned ${res.status}: ${res.statusText}`);
      }
      const data: DiscoveryResult = await res.json();
      setDiscovery(data);
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : "Discovery API unavailable";
      setDiscoveryError(msg);
      setDiscovery(null);
    } finally {
      setDiscoveryLoading(false);
    }
  }, []);

  // Phase 3: AI Workflow Review handler
  const handleReviewWorkflow = useCallback(
    async (wf: DiscoveredWorkflow) => {
      setActiveReviewWorkflow(wf);
      setReviewModalOpen(true);
      setWorkflowProposal(null);
      setAiLoading(true);
      setAiError(null);
      setApprovalStatus(workflowApprovals[wf.label] || "idle");

      try {
        const res = await fetch(`${API_BASE_URL}/api/ai/workflow/generate`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            workflow: wf,
            sequence: wf.sequence,
            context: {
              label: wf.label,
              occurrences: wf.occurrences,
              similarity: wf.similarity,
            },
          }),
        });

        if (!res.ok) {
          const errorData = await res.json().catch(() => ({}));
          throw new Error(
            errorData.detail || `Server returned ${res.status}: ${res.statusText}`
          );
        }

        const data = await res.json();
        if (data.success && data.workflow) {
          setWorkflowProposal(data.workflow);
        } else {
          throw new Error(data.error || "No workflow proposal generated");
        }
      } catch (err: unknown) {
        const msg =
          err instanceof Error
            ? err.message
            : "Failed to understand workflow with AI";
        setAiError(msg);
      } finally {
        setAiLoading(false);
      }
    },
    [workflowApprovals]
  );

  const handleApprove = () => {
    setApprovalStatus("approved");
    if (activeReviewWorkflow) {
      setWorkflowApprovals((prev) => ({
        ...prev,
        [activeReviewWorkflow.label]: "approved",
      }));
    }
  };

  const handleReject = () => {
    setApprovalStatus("rejected");
    if (activeReviewWorkflow) {
      setWorkflowApprovals((prev) => ({
        ...prev,
        [activeReviewWorkflow.label]: "rejected",
      }));
    }
  };

  // Initial load
  useEffect(() => {
    fetchData();
    fetchDiscovery();
  }, [fetchData, fetchDiscovery]);

  // Polling interval if autoRefresh is enabled (every 5 seconds)
  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(() => {
      fetchData(false);
      fetchDiscovery();
    }, 5000);
    return () => clearInterval(interval);
  }, [autoRefresh, fetchData, fetchDiscovery]);

  // Helper to extract customer identifier from event metadata
  const getCustomer = (metadata?: EventMetadata): string | null => {
    if (!metadata) return null;
    return (
      metadata.customer ||
      metadata.customer_name ||
      metadata.client ||
      metadata.name ||
      null
    );
  };

  // Formatter for timestamps
  const formatTime = (isoString: string) => {
    if (!mounted) {
      return { full: isoString, relative: "" };
    }
    try {
      const date = new Date(isoString);
      return {
        full: date.toLocaleString(undefined, {
          month: "short",
          day: "numeric",
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        }),
        relative: getRelativeTimeString(date),
      };
    } catch {
      return { full: isoString, relative: "" };
    }
  };

  const getRelativeTimeString = (date: Date) => {
    const diff = Math.floor((Date.now() - date.getTime()) / 1000);
    if (diff < 5) return "just now";
    if (diff < 60) return `${diff}s ago`;
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return `${Math.floor(diff / 86400)}d ago`;
  };

  // Dynamic application badge styling
  const getAppBadge = (app: string) => {
    const lower = app.toLowerCase();
    if (lower.includes("email")) {
      return "bg-purple-950/60 text-purple-300 border-purple-800/60";
    }
    if (lower.includes("crm")) {
      return "bg-sky-950/60 text-sky-300 border-sky-800/60";
    }
    if (lower.includes("browser") || lower.includes("web")) {
      return "bg-amber-950/60 text-amber-300 border-amber-800/60";
    }
    return "bg-zinc-800/80 text-zinc-300 border-zinc-700/60";
  };

  // Unique applications for filter
  const uniqueApps = useMemo(() => {
    const apps = new Set<string>();
    events.forEach((e) => {
      if (e.application) apps.add(e.application);
    });
    return Array.from(apps);
  }, [events]);

  // Unique event types
  const uniqueEventTypes = useMemo(() => {
    const types = new Set<string>();
    events.forEach((e) => {
      if (e.event_type) types.add(e.event_type);
    });
    return Array.from(types);
  }, [events]);

  // Filtered events
  const filteredEvents = useMemo(() => {
    return events.filter((ev) => {
      // App filter
      if (appFilter !== "ALL" && ev.application !== appFilter) {
        return false;
      }
      // Search term
      if (!searchTerm) return true;
      const term = searchTerm.toLowerCase();
      const customer = getCustomer(ev.metadata)?.toLowerCase() || "";
      const app = ev.application.toLowerCase();
      const type = ev.event_type.toLowerCase();
      const target = (ev.target || "").toLowerCase();
      const session = ev.session_id.toLowerCase();

      return (
        app.includes(term) ||
        type.includes(term) ||
        target.includes(term) ||
        customer.includes(term) ||
        session.includes(term)
      );
    });
  }, [events, appFilter, searchTerm]);

  // Helper: prettify event_type verb for display (e.g. open_email → Open Email)
  const formatEventStep = (step: string): string =>
    step
      .split("_")
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(" ");

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col font-sans">
      {/* Top Navigation / App Header */}
      <header className="border-b border-zinc-800/80 bg-zinc-900/40 backdrop-blur-md sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-cyan-600 via-indigo-600 to-purple-600 flex items-center justify-center shadow-lg shadow-cyan-900/30 ring-1 ring-white/10">
              <span className="text-white font-mono font-bold text-base tracking-tighter">W</span>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-lg font-bold tracking-tight text-white flex items-center gap-1.5">
                  WorkFlow<span className="text-cyan-400">OS</span>
                </h1>
                <span className="text-[10px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded bg-indigo-950/80 text-indigo-300 border border-indigo-700/60">
                  Phase 3 &amp; 4.1
                </span>
              </div>
              <p className="text-xs text-zinc-400">Observational Event Ingestion, Discovery &amp; AI Workflow Understanding</p>
            </div>
          </div>

          {/* Status Badges & Controls */}
          <div className="flex items-center gap-3">
            {/* Launch Demo Apps Button */}
            <Link
              href="/demo"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-gradient-to-r from-purple-900/60 via-indigo-900/60 to-cyan-900/60 hover:from-purple-800/80 hover:to-cyan-800/80 text-white border border-indigo-600/50 active:scale-95 transition shadow-sm cursor-pointer"
              title="Launch Phase 4.1 Demo Applications (Mail, CRM, Chat)"
            >
              <svg className="w-3.5 h-3.5 text-cyan-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
              </svg>
              <span>Demo Apps</span>
            </Link>

            {/* Backend Connection Indicator */}
            <div
              className={`flex items-center gap-2 px-2.5 py-1 rounded-full text-xs font-medium border transition-all ${
                backendStatus === "connected"
                  ? "bg-emerald-950/40 text-emerald-300 border-emerald-800/60"
                  : backendStatus === "checking"
                  ? "bg-yellow-950/40 text-yellow-300 border-yellow-800/60"
                  : "bg-rose-950/40 text-rose-300 border-rose-800/60"
              }`}
              title={`API endpoint: ${API_BASE_URL}`}
            >
              <span className="relative flex h-2 w-2">
                {backendStatus === "connected" && (
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                )}
                <span
                  className={`relative inline-flex rounded-full h-2 w-2 ${
                    backendStatus === "connected"
                      ? "bg-emerald-500"
                      : backendStatus === "checking"
                      ? "bg-yellow-500"
                      : "bg-rose-500"
                  }`}
                ></span>
              </span>
              <span className="hidden sm:inline">Backend:</span>
              <span className="capitalize">{backendStatus}</span>
            </div>

            {/* Agent Ingestion Status Badge */}
            <div className="hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-zinc-900 text-zinc-300 border border-zinc-800">
              <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse"></span>
              <span>Agent Stream: Active</span>
            </div>

            {/* Refresh Button */}
            <button
              onClick={() => fetchData(true)}
              disabled={refreshing}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border border-zinc-700 active:scale-95 transition-all disabled:opacity-60 cursor-pointer"
            >
              <svg
                className={`w-3.5 h-3.5 text-zinc-300 ${refreshing ? "animate-spin" : ""}`}
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                />
              </svg>
              <span>{refreshing ? "Refreshing..." : "Refresh Activity"}</span>
            </button>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        {/* KPI / Metric Cards */}
        <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Total Events */}
          <div className="bg-zinc-900/60 border border-zinc-800/80 rounded-xl p-4.5 shadow-sm relative overflow-hidden group hover:border-zinc-700 transition">
            <div className="absolute top-0 right-0 w-24 h-24 bg-cyan-500/5 rounded-full blur-2xl group-hover:bg-cyan-500/10 transition"></div>
            <div className="flex items-center justify-between text-zinc-400 mb-1">
              <span className="text-xs font-medium uppercase tracking-wider">Total Events</span>
              <svg className="w-4 h-4 text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <div className="text-2xl font-bold font-mono text-white mt-1">
              {loading ? (
                <div className="h-8 w-16 bg-zinc-800 rounded animate-pulse"></div>
              ) : (
                events.length
              )}
            </div>
            <p className="text-[11px] text-zinc-500 mt-1">Ingested via MongoDB /api/events</p>
          </div>

          {/* Active Applications */}
          <div className="bg-zinc-900/60 border border-zinc-800/80 rounded-xl p-4.5 shadow-sm relative overflow-hidden group hover:border-zinc-700 transition">
            <div className="absolute top-0 right-0 w-24 h-24 bg-purple-500/5 rounded-full blur-2xl group-hover:bg-purple-500/10 transition"></div>
            <div className="flex items-center justify-between text-zinc-400 mb-1">
              <span className="text-xs font-medium uppercase tracking-wider">Applications</span>
              <svg className="w-4 h-4 text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
              </svg>
            </div>
            <div className="text-2xl font-bold font-mono text-white mt-1">
              {loading ? (
                <div className="h-8 w-12 bg-zinc-800 rounded animate-pulse"></div>
              ) : (
                uniqueApps.length
              )}
            </div>
            <p className="text-[11px] text-zinc-500 mt-1 truncate">
              {uniqueApps.length > 0 ? uniqueApps.join(", ") : "None detected yet"}
            </p>
          </div>

          {/* Unique Event Types */}
          <div className="bg-zinc-900/60 border border-zinc-800/80 rounded-xl p-4.5 shadow-sm relative overflow-hidden group hover:border-zinc-700 transition">
            <div className="absolute top-0 right-0 w-24 h-24 bg-emerald-500/5 rounded-full blur-2xl group-hover:bg-emerald-500/10 transition"></div>
            <div className="flex items-center justify-between text-zinc-400 mb-1">
              <span className="text-xs font-medium uppercase tracking-wider">Action Types</span>
              <svg className="w-4 h-4 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
              </svg>
            </div>
            <div className="text-2xl font-bold font-mono text-white mt-1">
              {loading ? (
                <div className="h-8 w-12 bg-zinc-800 rounded animate-pulse"></div>
              ) : (
                uniqueEventTypes.length
              )}
            </div>
            <p className="text-[11px] text-zinc-500 mt-1">Distinct observational verbs</p>
          </div>

          {/* Backend Connection Card */}
          <div className="bg-zinc-900/60 border border-zinc-800/80 rounded-xl p-4.5 shadow-sm relative overflow-hidden group hover:border-zinc-700 transition">
            <div className="flex items-center justify-between text-zinc-400 mb-1">
              <span className="text-xs font-medium uppercase tracking-wider">Engine Status</span>
              <span className="text-[10px] font-mono text-zinc-500">{API_BASE_URL}</span>
            </div>
            <div className="flex items-center gap-2 mt-1">
              <div
                className={`w-3 h-3 rounded-full ${
                  backendStatus === "connected"
                    ? "bg-emerald-400 shadow-sm shadow-emerald-500/50"
                    : backendStatus === "checking"
                    ? "bg-yellow-400"
                    : "bg-rose-500 shadow-sm shadow-rose-500/50"
                }`}
              />
              <span className="text-base font-semibold text-white capitalize">
                {backendStatus === "connected" ? "FastAPI Online" : backendStatus}
              </span>
            </div>
            <p className="text-[11px] text-zinc-500 mt-1">
              {lastRefreshed ? `Polled ${getRelativeTimeString(lastRefreshed)}` : "Connecting..."}
            </p>
          </div>
        </section>

        {/* ──────────────────────────────────────────────────────────────
            Phase 2: WORKFLOW DISCOVERY SECTION
        ────────────────────────────────────────────────────────────── */}
        <section className="bg-zinc-900/50 border border-zinc-800/80 rounded-xl overflow-hidden shadow-sm">
          {/* Section header */}
          <div className="px-5 py-3.5 border-b border-zinc-800/80 flex items-center justify-between bg-zinc-900/30">
            <div className="flex items-center gap-2">
              <svg className="w-4 h-4 text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2m0 10V7m0 10a2 2 0 002 2h2a2 2 0 002-2V7a2 2 0 00-2-2h-2a2 2 0 00-2 2" />
              </svg>
              <h2 className="text-sm font-semibold tracking-tight text-white">Workflow Discovery</h2>
              <span className="text-[10px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded bg-indigo-950/60 text-indigo-300 border border-indigo-800/60">Phase 2</span>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-[11px] text-zinc-500 font-mono">GET /api/discovery/repeated</span>
              <button
                id="discovery-refresh-btn"
                onClick={() => { setDiscoveryLoading(true); fetchDiscovery(); }}
                className="flex items-center gap-1 px-2 py-1 rounded text-[11px] bg-zinc-800 hover:bg-zinc-700 text-zinc-300 border border-zinc-700 transition"
              >
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                Scan
              </button>
            </div>
          </div>

          {/* Body */}
          <div className="p-5">
            {/* Loading state */}
            {discoveryLoading ? (
              <div className="flex items-center gap-3 py-6">
                <div className="w-5 h-5 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin" />
                <span className="text-sm text-zinc-400">Scanning event history for repeated workflows...</span>
              </div>
            ) : discoveryError ? (
              /* Error state */
              <div className="bg-amber-950/30 border border-amber-800/60 rounded-lg p-4 flex items-start gap-3">
                <svg className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                <div>
                  <p className="text-sm font-medium text-amber-300">Discovery Unavailable</p>
                  <p className="text-xs text-amber-300/70 mt-0.5">{discoveryError}</p>
                  <p className="text-[11px] text-amber-400/60 mt-1">
                    Ensure the backend is running at <code className="bg-amber-900/30 px-1 rounded font-mono">{API_BASE_URL}</code>.
                  </p>
                </div>
              </div>
            ) : !discovery || !discovery.detected ? (
              /* No repeated workflow state */
              <div className="py-8 text-center">
                <div className="w-12 h-12 rounded-xl bg-zinc-800/60 border border-zinc-700/60 flex items-center justify-center mx-auto text-zinc-500 mb-3">
                  <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                </div>
                <h3 className="text-sm font-semibold text-zinc-300">No Repeated Workflows Detected</h3>
                <p className="text-xs text-zinc-500 mt-1 max-w-sm mx-auto">
                  WorkFlowOS needs at least 2 sessions sharing a sequence of ≥3 events to detect a pattern.
                </p>
                <div className="mt-4 inline-block text-left bg-zinc-950 border border-zinc-800 rounded-lg p-3 text-xs">
                  <p className="text-zinc-400 font-mono text-[11px] mb-1">Seed Phase 2 test data:</p>
                  <code className="text-indigo-400 font-mono select-all">
                    python backend/test_event.py --seed-workflows
                  </code>
                </div>
              </div>
            ) : (
              /* Detected workflows */
              <div className="space-y-5">
                {/* Detection banner */}
                <div className="flex items-center gap-3 bg-emerald-950/40 border border-emerald-800/60 rounded-lg px-4 py-3">
                  <span className="text-xl" role="img" aria-label="magnifier">🔍</span>
                  <div>
                    <p className="text-sm font-bold text-emerald-300">Repeated Workflow Detected</p>
                    <p className="text-xs text-emerald-400/70">
                      {discovery.workflows.length} workflow pattern{discovery.workflows.length > 1 ? "s" : ""} found across multiple sessions.
                    </p>
                  </div>
                </div>

                {/* Workflow cards */}
                {discovery.workflows.map((wf, idx) => (
                  <div
                    key={idx}
                    id={`workflow-card-${idx}`}
                    className="bg-zinc-950/70 border border-indigo-900/60 rounded-xl p-5 shadow-sm relative overflow-hidden"
                  >
                    {/* Glow accent */}
                    <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/5 via-transparent to-purple-500/5 pointer-events-none" />

                    {/* Workflow label & stats */}
                    <div className="flex flex-wrap items-start justify-between gap-4 mb-4">
                      <div>
                        <h3 className="text-base font-bold text-white">{wf.label}</h3>
                        <p className="text-xs text-zinc-400 mt-0.5">Deterministic workflow pattern (Phase 2)</p>
                      </div>
                      <div className="flex items-center gap-3 flex-wrap">
                        {/* Occurrences badge */}
                        <div className="flex flex-col items-center bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 min-w-[64px]">
                          <span className="text-lg font-bold font-mono text-indigo-300">{wf.occurrences}×</span>
                          <span className="text-[10px] text-zinc-500 uppercase tracking-wider">Repeated</span>
                        </div>
                        {/* Similarity badge */}
                        <div className="flex flex-col items-center bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 min-w-[64px]">
                          <span className="text-lg font-bold font-mono text-emerald-300">
                            {Math.round(wf.similarity * 100)}%
                          </span>
                          <span className="text-[10px] text-zinc-500 uppercase tracking-wider">Similarity</span>
                        </div>
                      </div>
                    </div>

                    {/* Sequence steps */}
                    <div className="mb-4">
                      <p className="text-[11px] font-medium uppercase tracking-wider text-zinc-500 mb-3">Workflow Steps</p>
                      <div className="flex flex-wrap items-center gap-1">
                        {wf.sequence.map((step, si) => (
                          <React.Fragment key={si}>
                            <span
                              className="inline-flex items-center px-2.5 py-1 rounded-lg text-xs font-mono font-medium
                                bg-indigo-950/60 text-indigo-200 border border-indigo-800/60"
                            >
                              {formatEventStep(step)}
                            </span>
                            {si < wf.sequence.length - 1 && (
                              <svg className="w-3.5 h-3.5 text-zinc-600 mx-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                              </svg>
                            )}
                          </React.Fragment>
                        ))}
                      </div>
                    </div>

                    {/* Session IDs */}
                    <div className="mb-5">
                      <p className="text-[11px] font-medium uppercase tracking-wider text-zinc-500 mb-2">Sessions</p>
                      <div className="flex flex-wrap gap-2">
                        {wf.session_ids.map((sid) => (
                          <span
                            key={sid}
                            className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-mono
                              bg-zinc-800/80 text-zinc-300 border border-zinc-700/60"
                          >
                            <span className="w-1.5 h-1.5 rounded-full bg-indigo-400"></span>
                            {sid}
                          </span>
                        ))}
                      </div>
                    </div>

                    {/* Action footer */}
                    <div className="flex items-center justify-between pt-4 border-t border-zinc-800/60">
                      <div>
                        {workflowApprovals[wf.label] === "approved" ? (
                          <div className="flex items-center gap-1.5 text-xs text-emerald-400 font-medium">
                            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                            <span>Workflow approved & ready for automation</span>
                          </div>
                        ) : workflowApprovals[wf.label] === "rejected" ? (
                          <div className="flex items-center gap-1.5 text-xs text-rose-400 font-medium">
                            <span className="w-2 h-2 rounded-full bg-rose-400"></span>
                            <span>Workflow rejected by human review</span>
                          </div>
                        ) : (
                          <p className="text-[11px] text-zinc-500 italic">
                            Infer intent & synthesize structured workflow with Gemini AI
                          </p>
                        )}
                      </div>
                      <button
                        id={`review-workflow-btn-${idx}`}
                        onClick={() => handleReviewWorkflow(wf)}
                        className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-semibold
                          bg-gradient-to-r from-indigo-600 via-indigo-500 to-cyan-600 hover:from-indigo-500 hover:to-cyan-500
                          text-white border border-indigo-500/50 shadow-md shadow-indigo-950/60
                          hover:shadow-indigo-500/20 active:scale-95 transition-all cursor-pointer"
                      >
                        <svg className="w-3.5 h-3.5 text-cyan-200" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                        </svg>
                        Review Workflow
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>
        {/* ── End Workflow Discovery ────────────────────────────────── */}

        {/* API Error Notification */}
        {error && (
          <div className="bg-rose-950/40 border border-rose-800/80 rounded-xl p-4 flex items-start justify-between gap-3 text-sm text-rose-200">
            <div className="flex items-start gap-3">
              <svg className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <div>
                <p className="font-semibold text-rose-300">Backend Communication Issue</p>
                <p className="text-xs text-rose-300/80 mt-0.5">{error}</p>
                <p className="text-[11px] text-rose-400/70 mt-1">
                  Ensure the FastAPI backend is running at <code className="bg-rose-900/40 px-1 py-0.5 rounded font-mono">{API_BASE_URL}</code>.
                </p>
              </div>
            </div>
            <button
              onClick={() => fetchData(true)}
              className="px-2.5 py-1 text-xs font-medium bg-rose-900/60 hover:bg-rose-800/80 border border-rose-700/80 rounded-md shrink-0 text-white transition"
            >
              Retry
            </button>
          </div>
        )}

        {/* Table Controls (Search, Filters, Auto-refresh toggle) */}
        <section className="bg-zinc-900/40 border border-zinc-800/80 rounded-xl p-3 sm:p-4 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
          <div className="flex flex-1 items-center gap-3">
            {/* Search Input */}
            <div className="relative flex-1 max-w-md">
              <svg
                className="w-4 h-4 text-zinc-500 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <input
                type="text"
                placeholder="Search by app, action, target, customer, session..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-800 rounded-lg pl-9 pr-8 py-1.5 text-xs text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition font-sans"
              />
              {searchTerm && (
                <button
                  onClick={() => setSearchTerm("")}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300 text-xs"
                >
                  ✕
                </button>
              )}
            </div>

            {/* App Filter Selector */}
            <select
              value={appFilter}
              onChange={(e) => setAppFilter(e.target.value)}
              className="bg-zinc-950 border border-zinc-800 text-zinc-300 text-xs rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-cyan-500 cursor-pointer"
            >
              <option value="ALL">All Applications</option>
              {uniqueApps.map((app) => (
                <option key={app} value={app}>
                  {app}
                </option>
              ))}
            </select>
          </div>

          {/* Right side controls: Auto-refresh switch */}
          <div className="flex items-center justify-between sm:justify-end gap-3 text-xs text-zinc-400">
            <label className="flex items-center gap-2 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
                className="sr-only peer"
              />
              <div className="w-8 h-4.5 bg-zinc-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-3.5 after:w-3.5 after:transition-all peer-checked:bg-cyan-600 relative"></div>
              <span>Live stream (5s)</span>
            </label>
            <span className="text-zinc-600">|</span>
            <span className="font-mono text-[11px] text-zinc-500">
              Showing {filteredEvents.length} of {events.length}
            </span>
          </div>
        </section>

        {/* Activity Table Card */}
        <section className="bg-zinc-900/50 border border-zinc-800/80 rounded-xl overflow-hidden shadow-sm">
          <div className="px-5 py-3.5 border-b border-zinc-800/80 flex items-center justify-between bg-zinc-900/30">
            <div className="flex items-center gap-2">
              <svg className="w-4 h-4 text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <h2 className="text-sm font-semibold tracking-tight text-white">Recent Activity Stream</h2>
            </div>
            <span className="text-[11px] text-zinc-500 font-mono">GET /api/events</span>
          </div>

          {/* Loading Skeleton State */}
          {loading ? (
            <div className="p-6 space-y-4">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="flex items-center justify-between gap-4 animate-pulse">
                  <div className="h-4 bg-zinc-800 rounded w-28"></div>
                  <div className="h-4 bg-zinc-800 rounded w-24"></div>
                  <div className="h-4 bg-zinc-800 rounded w-32"></div>
                  <div className="h-4 bg-zinc-800 rounded w-36"></div>
                  <div className="h-4 bg-zinc-800 rounded w-20"></div>
                </div>
              ))}
            </div>
          ) : filteredEvents.length === 0 ? (
            /* Empty State */
            <div className="py-16 px-4 text-center">
              <div className="w-12 h-12 rounded-xl bg-zinc-800/60 border border-zinc-700/60 flex items-center justify-center mx-auto text-zinc-500 mb-3">
                <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
                </svg>
              </div>
              <h3 className="text-sm font-semibold text-zinc-200">
                {events.length === 0 ? "No activity events captured yet" : "No events match current filter"}
              </h3>
              <p className="text-xs text-zinc-500 max-w-sm mx-auto mt-1">
                {events.length === 0
                  ? "Events will show up here in real time as the observational agent or tests submit user activity."
                  : "Try clearing your search query or application filter."}
              </p>
              {events.length === 0 && (
                <div className="mt-4 inline-block text-left bg-zinc-950 border border-zinc-800 rounded-lg p-3 text-xs">
                  <p className="text-zinc-400 font-mono text-[11px] mb-1">To send sample events run:</p>
                  <code className="text-cyan-400 font-mono select-all">
                    python backend/test_event.py --all
                  </code>
                </div>
              )}
            </div>
          ) : (
            /* Events Table */
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-zinc-800/80 bg-zinc-950/40 text-zinc-400 font-medium">
                    <th scope="col" className="py-3 px-4 sm:px-6">Timestamp</th>
                    <th scope="col" className="py-3 px-4">Application</th>
                    <th scope="col" className="py-3 px-4">Event Type</th>
                    <th scope="col" className="py-3 px-4">Target</th>
                    <th scope="col" className="py-3 px-4">Customer</th>
                    <th scope="col" className="py-3 px-4 text-right">Details</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800/60 font-sans">
                  {filteredEvents.map((ev) => {
                    const timeInfo = formatTime(ev.timestamp);
                    const customer = getCustomer(ev.metadata);
                    return (
                      <tr
                        key={ev.id}
                        className="hover:bg-zinc-800/30 transition group cursor-pointer"
                        onClick={() => setSelectedEvent(ev)}
                      >
                        {/* Timestamp */}
                        <td className="py-3 px-4 sm:px-6 whitespace-nowrap">
                          <div className="font-mono text-zinc-300 text-xs">{timeInfo.full}</div>
                          {timeInfo.relative && (
                            <div className="text-[10px] text-zinc-500">{timeInfo.relative}</div>
                          )}
                        </td>

                        {/* Application */}
                        <td className="py-3 px-4 whitespace-nowrap">
                          <span
                            className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-mono border ${getAppBadge(
                              ev.application
                            )}`}
                          >
                            {ev.application}
                          </span>
                        </td>

                        {/* Event Type */}
                        <td className="py-3 px-4 whitespace-nowrap">
                          <span className="font-mono font-medium text-cyan-300 bg-cyan-950/30 px-2 py-0.5 rounded border border-cyan-800/40 text-[11px]">
                            {ev.event_type}
                          </span>
                        </td>

                        {/* Target */}
                        <td className="py-3 px-4 max-w-xs truncate text-zinc-300 font-mono text-[11px]">
                          {ev.target ? (
                            <span title={ev.target}>{ev.target}</span>
                          ) : (
                            <span className="text-zinc-600">—</span>
                          )}
                        </td>

                        {/* Customer from metadata */}
                        <td className="py-3 px-4 whitespace-nowrap">
                          {customer ? (
                            <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-medium bg-emerald-950/50 text-emerald-300 border border-emerald-800/60">
                              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
                              {customer}
                            </span>
                          ) : (
                            <span className="text-zinc-600">—</span>
                          )}
                        </td>

                        {/* Details / Action */}
                        <td className="py-3 px-4 text-right whitespace-nowrap">
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              setSelectedEvent(ev);
                            }}
                            className="text-zinc-400 hover:text-cyan-400 font-mono text-[11px] underline underline-offset-2 decoration-zinc-700 hover:decoration-cyan-400 transition"
                          >
                            Inspect
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </main>

      {/* ──────────────────────────────────────────────────────────────
          Phase 3: AI WORKFLOW PROPOSAL REVIEW MODAL
      ────────────────────────────────────────────────────────────── */}
      {reviewModalOpen && activeReviewWorkflow && (
        <div
          className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4 z-50 animate-fadeIn"
          onClick={() => {
            if (!aiLoading) setReviewModalOpen(false);
          }}
        >
          <div
            id="workflow-review-modal"
            className="bg-zinc-900 border border-zinc-700/80 rounded-2xl max-w-2xl w-full p-6 sm:p-7 shadow-2xl relative max-h-[90vh] flex flex-col overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="flex items-start justify-between pb-4 border-b border-zinc-800 shrink-0">
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs font-bold text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 via-indigo-300 to-purple-400 uppercase tracking-wider">
                    AI Workflow Proposal
                  </span>
                  <span className="text-zinc-600">•</span>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-950/70 text-indigo-300 border border-indigo-800/60">
                    Phase 3 • Gemini SDK
                  </span>
                </div>
                <h3 className="text-xl font-bold text-white mt-1">
                  {workflowProposal ? workflowProposal.name : activeReviewWorkflow.label}
                </h3>
              </div>
              <button
                onClick={() => setReviewModalOpen(false)}
                disabled={aiLoading}
                className="text-zinc-400 hover:text-white p-1 rounded-lg hover:bg-zinc-800 transition disabled:opacity-40 cursor-pointer"
              >
                ✕
              </button>
            </div>

            {/* Modal Body */}
            <div className="py-4 space-y-4 overflow-y-auto pr-1">
              {/* 1. Loading State */}
              {aiLoading && (
                <div className="py-14 text-center space-y-4">
                  <div className="relative w-14 h-14 mx-auto">
                    <div className="absolute inset-0 rounded-full border-2 border-indigo-500/30 animate-ping"></div>
                    <div className="w-14 h-14 rounded-full border-2 border-indigo-500 border-t-cyan-400 animate-spin"></div>
                  </div>
                  <div>
                    <h4 className="text-base font-semibold text-white">
                      Understanding workflow with AI...
                    </h4>
                    <p className="text-xs text-zinc-400 max-w-sm mx-auto mt-1">
                      Gemini is analyzing the observed sequence across sessions to infer user intent, trigger, actions, and dynamic variables.
                    </p>
                  </div>
                  <div className="flex flex-wrap justify-center gap-1.5 pt-2">
                    {activeReviewWorkflow.sequence.map((step, idx) => (
                      <span
                        key={idx}
                        className="px-2.5 py-1 rounded text-xs font-mono bg-zinc-800/80 text-zinc-300 border border-zinc-700/60"
                      >
                        {formatEventStep(step)}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* 2. Error State */}
              {!aiLoading && aiError && (
                <div className="py-6 space-y-4">
                  <div className="bg-rose-950/40 border border-rose-800/80 rounded-xl p-4 flex items-start gap-3">
                    <svg className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                    <div>
                      <p className="text-sm font-semibold text-rose-300">Workflow Understanding Unavailable</p>
                      <p className="text-xs text-rose-300/80 mt-1">{aiError}</p>
                      <p className="text-[11px] text-zinc-400 mt-2">
                        Verify that <code className="text-indigo-300">GEMINI_API_KEY</code> is configured in <code className="text-zinc-300">.env</code> and that the backend server is reachable.
                      </p>
                    </div>
                  </div>
                  <div className="flex justify-end gap-2">
                    <button
                      onClick={() => setReviewModalOpen(false)}
                      className="px-3.5 py-1.5 rounded-lg text-xs bg-zinc-800 hover:bg-zinc-700 text-zinc-300 transition cursor-pointer"
                    >
                      Dismiss
                    </button>
                    <button
                      onClick={() => handleReviewWorkflow(activeReviewWorkflow)}
                      className="px-4 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white transition flex items-center gap-1.5 cursor-pointer"
                    >
                      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                      </svg>
                      Retry Analysis
                    </button>
                  </div>
                </div>
              )}

              {/* 3. Generated Proposal Content */}
              {!aiLoading && !aiError && workflowProposal && (
                <>
                  {/* Intent */}
                  <div className="bg-zinc-950/80 rounded-xl p-4 border border-zinc-800">
                    <span className="text-[10px] font-mono uppercase tracking-wider text-indigo-400 font-semibold block mb-1">
                      Intent
                    </span>
                    <p className="text-sm text-zinc-200 leading-relaxed">
                      {workflowProposal.intent}
                    </p>
                  </div>

                  {/* Trigger */}
                  <div className="bg-zinc-950/80 rounded-xl p-4 border border-zinc-800">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-[10px] font-mono uppercase tracking-wider text-cyan-400 font-semibold">
                        Trigger
                      </span>
                      <span className={`px-2 py-0.5 rounded text-[10px] font-mono border ${getAppBadge(workflowProposal.trigger.application)}`}>
                        {workflowProposal.trigger.application}
                      </span>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-xs text-white font-medium bg-zinc-850 px-2 py-0.5 rounded border border-zinc-700">
                        {workflowProposal.trigger.type}
                      </span>
                      <span className="text-xs text-zinc-300">
                        {workflowProposal.trigger.description}
                      </span>
                    </div>
                  </div>

                  {/* Ordered Actions */}
                  <div className="bg-zinc-950/80 rounded-xl p-4 border border-zinc-800">
                    <div className="flex items-center justify-between mb-3">
                      <span className="text-[10px] font-mono uppercase tracking-wider text-purple-400 font-semibold">
                        Actions ({workflowProposal.actions.length} Ordered Steps)
                      </span>
                      <span className="text-[10px] text-zinc-500 font-mono">Strict execution order</span>
                    </div>
                    <div className="space-y-2">
                      {workflowProposal.actions.map((act, aIdx) => (
                        <div
                          key={aIdx}
                          className="flex items-start justify-between gap-3 p-2.5 rounded-lg bg-zinc-900/60 border border-zinc-800/60"
                        >
                          <div className="flex items-start gap-3">
                            <span className="w-5 h-5 rounded-full bg-indigo-950 text-indigo-300 border border-indigo-800/80 flex items-center justify-center text-xs font-mono font-bold shrink-0 mt-0.5">
                              {aIdx + 1}
                            </span>
                            <div>
                              <p className="text-xs font-medium text-white">{act.description}</p>
                              <div className="flex items-center gap-2 mt-1 flex-wrap">
                                <span className="font-mono text-[11px] text-cyan-300 bg-cyan-950/30 px-1.5 py-0.5 rounded border border-cyan-800/40">
                                  {act.type}
                                </span>
                                {act.target && (
                                  <span className="font-mono text-[11px] text-zinc-400">
                                    Target: <code className="text-zinc-300">{act.target}</code>
                                  </span>
                                )}
                              </div>
                            </div>
                          </div>
                          <span className={`px-2 py-0.5 rounded text-[10px] font-mono border shrink-0 ${getAppBadge(act.application)}`}>
                            {act.application}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Variables and Applications */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {/* Variables */}
                    <div className="bg-zinc-950/80 rounded-xl p-4 border border-zinc-800">
                      <span className="text-[10px] font-mono uppercase tracking-wider text-amber-400 font-semibold block mb-2">
                        Variables
                      </span>
                      <div className="flex flex-wrap gap-1.5">
                        {workflowProposal.variables && workflowProposal.variables.length > 0 ? (
                          workflowProposal.variables.map((v, vi) => (
                            <span
                              key={vi}
                              className="inline-flex items-center gap-1 px-2.5 py-1 rounded text-xs font-mono bg-amber-950/40 text-amber-300 border border-amber-800/60"
                            >
                              <span className="text-amber-500 font-bold">$</span>
                              {v}
                            </span>
                          ))
                        ) : (
                          <span className="text-xs text-zinc-500 italic">No dynamic variables detected</span>
                        )}
                      </div>
                    </div>

                    {/* Applications */}
                    <div className="bg-zinc-950/80 rounded-xl p-4 border border-zinc-800">
                      <span className="text-[10px] font-mono uppercase tracking-wider text-emerald-400 font-semibold block mb-2">
                        Applications
                      </span>
                      <div className="flex flex-wrap gap-1.5">
                        {workflowProposal.applications.map((app, ai) => (
                          <span
                            key={ai}
                            className={`px-2.5 py-1 rounded text-xs font-mono border ${getAppBadge(app)}`}
                          >
                            {app}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>

                  {/* Approval State Banners */}
                  {approvalStatus === "approved" && (
                    <div className="bg-emerald-950/60 border border-emerald-500/60 rounded-xl p-4 flex items-center gap-3 shadow-lg shadow-emerald-950/30 animate-fadeIn">
                      <div className="w-8 h-8 rounded-full bg-emerald-500/20 text-emerald-300 flex items-center justify-center text-base font-bold shrink-0">
                        ✓
                      </div>
                      <div>
                        <p className="text-sm font-bold text-emerald-200">
                          Workflow approved and ready for automation.
                        </p>
                        <p className="text-xs text-emerald-400/80 mt-0.5">
                          Phase 3 human review complete. Browser and application automation will execute in Phase 4.
                        </p>
                      </div>
                    </div>
                  )}

                  {approvalStatus === "rejected" && (
                    <div className="bg-zinc-950/80 border border-rose-800/60 rounded-xl p-4 flex items-center gap-3 animate-fadeIn">
                      <div className="w-8 h-8 rounded-full bg-rose-500/20 text-rose-300 flex items-center justify-center text-base font-bold shrink-0">
                        ✕
                      </div>
                      <div>
                        <p className="text-sm font-bold text-rose-200">Workflow rejected.</p>
                        <p className="text-xs text-zinc-400 mt-0.5">
                          This workflow proposal was dismissed by human operator. No automation will be created.
                        </p>
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>

            {/* Modal Footer / Approval Controls */}
            {!aiLoading && !aiError && workflowProposal && (
              <div className="pt-4 border-t border-zinc-800 flex items-center justify-between gap-4 shrink-0">
                {approvalStatus === "idle" ? (
                  <>
                    <div className="flex items-center gap-1.5 text-xs text-amber-400/90 font-medium">
                      <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                      </svg>
                      <span>Human review required before automation (Phase 3)</span>
                    </div>
                    <div className="flex items-center gap-2.5">
                      <button
                        id="reject-workflow-btn"
                        onClick={handleReject}
                        className="px-4 py-2 bg-zinc-800 hover:bg-rose-950/60 hover:text-rose-200 hover:border-rose-700/60 border border-zinc-700 text-zinc-300 rounded-lg text-xs font-semibold transition active:scale-95 cursor-pointer"
                      >
                        Reject
                      </button>
                      <button
                        id="approve-workflow-btn"
                        onClick={handleApprove}
                        className="px-5 py-2 bg-gradient-to-r from-emerald-600 via-teal-600 to-cyan-600 hover:from-emerald-500 hover:to-cyan-500 border border-emerald-500/50 text-white rounded-lg text-xs font-semibold shadow-lg shadow-emerald-950/50 hover:shadow-emerald-500/20 transition active:scale-95 cursor-pointer"
                      >
                        Approve Workflow
                      </button>
                    </div>
                  </>
                ) : (
                  <div className="w-full flex items-center justify-between">
                    <span className="text-xs text-zinc-500">Human decision recorded in session state</span>
                    <button
                      onClick={() => setReviewModalOpen(false)}
                      className="px-4 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 rounded-lg text-xs font-medium transition cursor-pointer"
                    >
                      Close
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Raw Event Modal / Drawer */}
      {selectedEvent && (
        <div
          className="fixed inset-0 bg-black/70 backdrop-blur-xs flex items-center justify-center p-4 z-50 animate-fadeIn"
          onClick={() => setSelectedEvent(null)}
        >
          <div
            className="bg-zinc-900 border border-zinc-700/80 rounded-2xl max-w-2xl w-full p-6 shadow-2xl relative"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="flex items-start justify-between pb-4 border-b border-zinc-800">
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs text-cyan-400 uppercase tracking-wider">Event Details</span>
                  <span className="text-zinc-600">•</span>
                  <span className="font-mono text-xs text-zinc-400">ID: {selectedEvent.id}</span>
                </div>
                <h3 className="text-lg font-bold text-white mt-1">
                  {selectedEvent.application} / {selectedEvent.event_type}
                </h3>
              </div>
              <button
                onClick={() => setSelectedEvent(null)}
                className="text-zinc-400 hover:text-white p-1 rounded-lg hover:bg-zinc-800 transition"
              >
                ✕
              </button>
            </div>

            {/* Modal Body */}
            <div className="py-4 space-y-4 text-xs font-mono">
              <div className="grid grid-cols-2 gap-3 bg-zinc-950 p-3 rounded-lg border border-zinc-800">
                <div>
                  <span className="text-zinc-500 block text-[10px] uppercase">Session ID</span>
                  <span className="text-zinc-200">{selectedEvent.session_id}</span>
                </div>
                <div>
                  <span className="text-zinc-500 block text-[10px] uppercase">Timestamp</span>
                  <span className="text-zinc-200">{selectedEvent.timestamp}</span>
                </div>
                <div>
                  <span className="text-zinc-500 block text-[10px] uppercase">Target</span>
                  <span className="text-zinc-200">{selectedEvent.target || "null"}</span>
                </div>
                <div>
                  <span className="text-zinc-500 block text-[10px] uppercase">Customer Metadata</span>
                  <span className="text-emerald-400 font-semibold">
                    {getCustomer(selectedEvent.metadata) || "None"}
                  </span>
                </div>
              </div>

              <div>
                <span className="text-zinc-400 font-sans text-xs font-semibold block mb-1.5">
                  Raw Event JSON (MongoDB Document)
                </span>
                <pre className="bg-zinc-950 p-3.5 rounded-lg border border-zinc-800 text-zinc-300 overflow-x-auto text-[11px] max-h-60">
                  {JSON.stringify(selectedEvent, null, 2)}
                </pre>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="pt-3 border-t border-zinc-800 flex justify-end">
              <button
                onClick={() => setSelectedEvent(null)}
                className="px-4 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 rounded-lg text-xs font-medium transition"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Footer */}
      <footer className="border-t border-zinc-800/80 bg-zinc-950 text-zinc-500 text-xs py-4 mt-auto">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-2">
          <p>© 2026 WorkFlowOS. Phase 3 — AI Workflow Understanding Engine.</p>
          <div className="flex items-center gap-4 text-[11px]">
            <span>FastAPI: <code className="text-zinc-400">{API_BASE_URL}</code></span>
            <span>•</span>
            <span>MongoDB Atlas</span>
            <span>•</span>
            <span className="text-indigo-400/70">AI: /api/ai/workflow/generate</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
