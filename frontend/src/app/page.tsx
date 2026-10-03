"use client";

import React, { useState, useEffect, useCallback } from "react";
import Sidebar from "@/components/Sidebar";
import Header from "@/components/Header";
import DashboardView from "@/components/views/DashboardView";
import ActivityView from "@/components/views/ActivityView";
import DiscoveryView from "@/components/views/DiscoveryView";
import BuilderView from "@/components/views/BuilderView";
import ExecutionsView from "@/components/views/ExecutionsView";
import SettingsView from "@/components/views/SettingsView";
import {
  ViewId,
  ActivityEvent,
  DiscoveryResult,
  AutomationExecutionRecord,
} from "@/lib/types";
import { API_BASE_URL } from "@/lib/utils";

export default function WorkFlowOSApp() {
  const [activeView, setActiveView] = useState<ViewId>("dashboard");

  // Connection & data
  const [backendStatus, setBackendStatus] = useState<"connected" | "disconnected" | "checking">("checking");
  const [lastRefreshed, setLastRefreshed] = useState<Date | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  // Events
  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const [eventsLoading, setEventsLoading] = useState(true);

  // Discovery
  const [discovery, setDiscovery] = useState<DiscoveryResult | null>(null);
  const [discoveryLoading, setDiscoveryLoading] = useState(true);
  const [discoveryError, setDiscoveryError] = useState<string | null>(null);

  // Executions
  const [executions, setExecutions] = useState<AutomationExecutionRecord[]>([]);
  const [executionsLoading, setExecutionsLoading] = useState(false);

  const fetchEvents = useCallback(async () => {
    try {
      const [healthRes, eventsRes] = await Promise.allSettled([
        fetch(`${API_BASE_URL}/health`, { cache: "no-store" }),
        fetch(`${API_BASE_URL}/api/events?limit=100`, { cache: "no-store" }),
      ]);

      setBackendStatus(
        healthRes.status === "fulfilled" && healthRes.value.ok ? "connected" : "disconnected"
      );

      if (eventsRes.status === "fulfilled" && eventsRes.value.ok) {
        const data: ActivityEvent[] = await eventsRes.value.json();
        setEvents(data);
        setBackendStatus("connected");
      }
      setLastRefreshed(new Date());
    } catch {
      setBackendStatus("disconnected");
    } finally {
      setEventsLoading(false);
    }
  }, []);

  const fetchDiscovery = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/discovery/repeated`, { cache: "no-store" });
      if (!res.ok) throw new Error(`Discovery API returned ${res.status}`);
      const data: DiscoveryResult = await res.json();
      setDiscovery(data);
      setDiscoveryError(null);
    } catch (e: unknown) {
      setDiscoveryError(e instanceof Error ? e.message : "Discovery unavailable");
      setDiscovery(null);
    } finally {
      setDiscoveryLoading(false);
    }
  }, []);

  const fetchExecutions = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/automation/executions`, { cache: "no-store" });
      if (res.ok) {
        const data = await res.json();
        const list: AutomationExecutionRecord[] = data.executions || [];
        setExecutions([...list].reverse());
      }
    } catch {
      // silent — executions is optional
    } finally {
      setExecutionsLoading(false);
    }
  }, []);

  const handleRefresh = useCallback(async (isManual = true) => {
    if (isManual) setRefreshing(true);
    await Promise.all([fetchEvents(), fetchDiscovery(), fetchExecutions()]);
    if (isManual) setRefreshing(false);
  }, [fetchEvents, fetchDiscovery, fetchExecutions]);

  // Initial load
  useEffect(() => {
    let isMounted = true;
    const load = async () => {
      if (!isMounted) return;
      await Promise.all([fetchEvents(), fetchDiscovery(), fetchExecutions()]);
    };
    load();
    return () => {
      isMounted = false;
    };
  }, [fetchEvents, fetchDiscovery, fetchExecutions]);

  // Auto-refresh every 5 s
  useEffect(() => {
    const id = setInterval(() => {
      fetchEvents();
      fetchDiscovery();
      fetchExecutions();
    }, 5000);
    return () => clearInterval(id);
  }, [fetchEvents, fetchDiscovery, fetchExecutions]);

  const handleRefreshDiscovery = useCallback(async () => {
    setDiscoveryLoading(true);
    await fetchDiscovery();
  }, [fetchDiscovery]);

  return (
    <div className="flex h-screen overflow-hidden bg-[#F7F9FC] text-[#475569]">
      {/* Sidebar */}
      <Sidebar
        activeView={activeView}
        onNavigate={setActiveView}
        backendStatus={backendStatus}
        eventCount={events.length}
        executionCount={executions.length}
        discoveryCount={discovery?.workflows.length ?? 0}
      />

      {/* Main content area */}
      <div className="flex flex-col flex-1 overflow-hidden">
        <Header
          activeView={activeView}
          backendStatus={backendStatus}
          lastRefreshed={lastRefreshed}
          refreshing={refreshing}
          onRefresh={() => handleRefresh(true)}
        />

        {/* View content — scrollable */}
        <main className="flex-1 overflow-y-auto">
          {activeView === "dashboard" && (
            <DashboardView
              events={events}
              executions={executions}
              discovery={discovery}
              loading={eventsLoading}
              historyLoading={executionsLoading}
              onNavigate={(v) => setActiveView(v)}
            />
          )}
          {activeView === "activity" && (
            <ActivityView
              events={events}
              loading={eventsLoading}
            />
          )}
          {activeView === "discovery" && (
            <DiscoveryView
              discovery={discovery}
              discoveryLoading={discoveryLoading}
              discoveryError={discoveryError}
              onRefreshDiscovery={handleRefreshDiscovery}
              onExecutionComplete={fetchExecutions}
            />
          )}
          {activeView === "builder" && (
            <BuilderView onExecutionComplete={fetchExecutions} />
          )}
          {activeView === "executions" && (
            <ExecutionsView
              executions={executions}
              loading={executionsLoading}
              onRefresh={fetchExecutions}
            />
          )}
          {activeView === "settings" && <SettingsView />}
        </main>
      </div>
    </div>
  );
}
