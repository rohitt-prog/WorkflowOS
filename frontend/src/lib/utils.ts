// Shared utility functions

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://localhost:8000";

export const getActionDisplayLabel = (actionType: string): string => {
  switch (actionType) {
    case "open_email": return "Open email";
    case "download_attachment": return "Download attachment";
    case "search_customer": return "Search customer";
    case "update_customer": return "Update customer";
    case "send_message": return "Send message";
    default:
      return actionType.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  }
};

export const getApplicationDisplayName = (appName?: string): string => {
  if (!appName) return "WorkFlow App";
  switch (appName) {
    case "demo_email": return "WorkFlow Mail";
    case "demo_crm": return "WorkFlow CRM";
    case "demo_chat":
    case "demo_messaging": return "WorkFlow Chat";
    default:
      return appName.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  }
};

export const getAppBadgeClass = (app: string): string => {
  const lower = app.toLowerCase();
  if (lower.includes("email") || lower.includes("mail")) {
    return "bg-purple-50 text-purple-700 border-purple-200/80";
  }
  if (lower.includes("crm")) {
    return "bg-sky-50 text-sky-700 border-sky-200/80";
  }
  if (lower.includes("browser") || lower.includes("web")) {
    return "bg-amber-50 text-amber-700 border-amber-200/80";
  }
  if (lower.includes("chat") || lower.includes("message")) {
    return "bg-emerald-50 text-emerald-700 border-emerald-200/80";
  }
  return "bg-slate-100 text-slate-700 border-slate-200";
};

export const formatEventStep = (step: string): string =>
  step.split("_").map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");

export const getRelativeTime = (date: Date): string => {
  const diff = Math.floor((Date.now() - date.getTime()) / 1000);
  if (diff < 5) return "just now";
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
};

export const formatTimestamp = (
  isoString: string,
  mounted: boolean = true
): { full: string; relative: string } => {
  if (!mounted) return { full: isoString, relative: "" };
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
      relative: getRelativeTime(date),
    };
  } catch {
    return { full: isoString, relative: "" };
  }
};

export const statusBadgeConfig = (
  status: string
): { label: string; className: string; dot?: string } => {
  switch (status) {
    case "completed":
      return {
        label: "Completed",
        className: "bg-emerald-50 border-emerald-200 text-emerald-700 font-medium",
        dot: "bg-emerald-600",
      };
    case "paused":
      return {
        label: "Paused",
        className: "bg-amber-50 border-amber-200 text-amber-700 font-medium",
        dot: "bg-amber-500",
      };
    case "running":
      return {
        label: "Running",
        className: "bg-blue-50 border-blue-200 text-blue-700 font-medium",
        dot: "bg-blue-600 animate-ping",
      };
    case "failed":
      return {
        label: "Failed",
        className: "bg-rose-50 border-rose-200 text-rose-700 font-medium",
        dot: "bg-rose-600",
      };
    case "cancelled":
      return {
        label: "Cancelled",
        className: "bg-slate-100 border-slate-200 text-slate-600 font-medium",
      };
    case "pending":
      return {
        label: "Pending",
        className: "bg-amber-50 border-amber-200 text-amber-700 font-medium",
        dot: "bg-amber-500",
      };
    default:
      return {
        label: status,
        className: "bg-slate-100 border-slate-200 text-slate-700 font-medium",
      };
  }
};
