"use client";

import React, { useState, useEffect, useCallback } from "react";
import Sidebar from "@/components/Sidebar";
import Header from "@/components/Header";
import DashboardView from "@/components/views/DashboardView";
import ActivityView from "@/components/views/ActivityView";
import WorkflowsView from "@/components/views/WorkflowsView";
import BuilderView from "@/components/views/BuilderView";
import ExecutionsView from "@/components/views/ExecutionsView";
import ApplicationsView from "@/components/views/ApplicationsView";
import SettingsView from "@/components/views/SettingsView";
import {
  ViewId,
  ActivityEvent,
  DiscoveryResult,
  AutomationExecutionRecord,
  SystemStatusResponse,
} from "@/lib/types";
import {
  fetchSystemStatus,
  fetchEvents,
  fetchDiscoveredWorkflows,
  fetchExecutions,
} from "@/lib/api";

export default function WorkFlowOSApp() {
  const [activeView, setActiveView] = useState<ViewId>("dashboard");

  // Connection & System Telemetry
  const [backendStatus, setBackendStatus] = useState<"connected" | "disconnected" | "checking">("checking");
  const [systemStatus, setSystemStatus] = useState<SystemStatusResponse | null>(null);
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

  const loadSystemData = useCallback(async () => {
    try {
      const statusData = await fetchSystemStatus();
      setSystemStatus(statusData);
      setBackendStatus("connected");
    } catch {
      setBackendStatus("disconnected");
    }
  }, []);

  const loadEventsData = useCallback(async () => {
    try {
      const data = await fetchEvents({ limit: 100 });
      setEvents(data);
      setBackendStatus("connected");
      setLastRefreshed(new Date());
    } catch {
      // handled gracefully
    } finally {
      setEventsLoading(false);
    }
  }, []);

  const loadDiscoveryData = useCallback(async () => {
    try {
      const data = await fetchDiscoveredWorkflows(true);
      setDiscovery(data);
      setDiscoveryError(null);
    } catch (e: unknown) {
      setDiscoveryError(e instanceof Error ? e.message : "Discovery scan unavailable");
      setDiscovery(null);
    } finally {
      setDiscoveryLoading(false);
    }
  }, []);

  const loadExecutionsData = useCallback(async () => {
    try {
      const list = await fetchExecutions();
      setExecutions(list);
    } catch {
      // executions is optional
    } finally {
      setExecutionsLoading(false);
    }
  }, []);

  const handleRefresh = useCallback(
    async (isManual = true) => {
      if (isManual) setRefreshing(true);
      await Promise.allSettled([
        loadSystemData(),
        loadEventsData(),
        loadDiscoveryData(),
        loadExecutionsData(),
      ]);
      setLastRefreshed(new Date());
      if (isManual) setRefreshing(false);
    },
    [loadSystemData, loadEventsData, loadDiscoveryData, loadExecutionsData]
  );

  // Initial load
  useEffect(() => {
    let isMounted = true;
    const load = async () => {
      if (!isMounted) return;
      await handleRefresh(false);
    };
    load();
    return () => {
      isMounted = false;
    };
  }, [handleRefresh]);

  // Periodic background telemetry refresh every 6 seconds
  useEffect(() => {
    const id = setInterval(() => {
      handleRefresh(false);
    }, 6000);
    return () => clearInterval(id);
  }, [handleRefresh]);

  const handleRefreshDiscovery = useCallback(async () => {
    setDiscoveryLoading(true);
    await loadDiscoveryData();
  }, [loadDiscoveryData]);

  return (
    <div className="flex h-screen overflow-hidden bg-[#F7F9FC] text-[#475569]">
      {/* Sidebar Navigation */}
      <Sidebar
        activeView={activeView}
        onNavigate={setActiveView}
        backendStatus={backendStatus}
        eventCount={events.length}
        executionCount={executions.length}
        discoveryCount={discovery?.workflows.length ?? 0}
      />

      {/* Main Content Area */}
      <div className="flex flex-col flex-1 overflow-hidden">
        <Header
          activeView={activeView}
          backendStatus={backendStatus}
          lastRefreshed={lastRefreshed}
          refreshing={refreshing}
          onRefresh={() => handleRefresh(true)}
        />

        {/* View Content Container */}
        <main className="flex-1 overflow-y-auto">
          {activeView === "dashboard" && (
            <DashboardView
              events={events}
              executions={executions}
              discovery={discovery}
              systemStatus={systemStatus}
              loading={eventsLoading}
              historyLoading={executionsLoading}
              onNavigate={setActiveView}
              onRefresh={loadEventsData}
            />
          )}

          {activeView === "activity" && (
            <ActivityView
              events={events}
              loading={eventsLoading}
            />
          )}

          {(activeView === "workflows" || activeView === "discovery") && (
            <WorkflowsView
              discovery={discovery}
              discoveryLoading={discoveryLoading}
              discoveryError={discoveryError}
              onRefreshDiscovery={handleRefreshDiscovery}
              onExecutionComplete={loadExecutionsData}
              onNavigate={setActiveView}
            />
          )}

          {activeView === "builder" && (
            <BuilderView
              onExecutionComplete={loadExecutionsData}
              onNavigate={setActiveView}
            />
          )}

          {activeView === "executions" && (
            <ExecutionsView
              executions={executions}
              loading={executionsLoading}
              onRefresh={loadExecutionsData}
            />
          )}

          {activeView === "applications" && <ApplicationsView />}

          {activeView === "settings" && <SettingsView />}
        </main>
      </div>
    </div>
  );
}
