// Shared utility functions

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://127.0.0.1:8000";

export const getActionDisplayLabel = (actionType: string): string => {
  switch (actionType) {
    case "open_email": return "Open email";
    case "download_attachment": return "Download attachment";
    case "list_recent_messages": return "List recent emails";
    case "search_customer": return "Search customer";
    case "update_customer": return "Update customer";
    case "send_message": return "Send message";
    default:
      return actionType.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  }
};

export const getApplicationDisplayName = (appName?: string): string => {
  if (!appName) return "WorkFlow App";
  switch (appName.toLowerCase()) {
    case "demo_email": return "WorkFlow Mail";
    case "demo_crm": return "WorkFlow CRM";
    case "demo_chat":
    case "demo_messaging": return "WorkFlow Chat";
    case "gmail": return "Google Gmail";
    default:
      return appName.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  }
};

export const getAppBadgeClass = (app: string): string => {
  const lower = app.toLowerCase();
  if (lower.includes("gmail")) {
    return "bg-rose-50 text-rose-700 border-rose-200/80";
  }
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

/**
 * Sanitizes an error message string to ensure tokens, authorization headers,
 * client secrets, and sensitive credentials are never displayed in the UI.
 */
export function sanitizeErrorMessage(message: string): string {
  if (!message || typeof message !== "string") return "";
  return message
    .replace(/(bearer\s+)[A-Za-z0-9\-._~+/]+=*/gi, "$1[REDACTED]")
    .replace(/(basic\s+)[A-Za-z0-9+/=]+/gi, "$1[REDACTED]")
    .replace(/(ya29\.[A-Za-z0-9\-._~+/]+)/gi, "[REDACTED]")
    .replace(/(1\/\/[A-Za-z0-9\-._~+/]+)/gi, "[REDACTED]")
    .replace(/((?:^|[\s?&])(?:token|access_token|refresh_token|client_secret|client_id|key|api_key|password)=)[^&\s]+/gi, "$1[REDACTED]")
    .replace(/("(?:token|access_token|refresh_token|client_secret|client_id|api_key|password)":\s*")[^"]+(")/gi, "$1[REDACTED]$2");
}

/**
 * Parses and formats backend API error responses into clean, human-readable strings.
 * Safely handles:
 * - FastAPI/Pydantic validation errors (array of { loc, msg, type } dicts)
 * - FastAPI HTTPException detail strings or objects
 * - Direct error arrays or standard Error objects
 * - Plain strings or unexpected object structures
 *
 * Avoids "[object Object]" coercion and redacts sensitive credentials.
 */
export function formatApiErrorMessage(
  errData: unknown,
  fallbackMessage: string = "Request failed"
): string {
  if (!errData) {
    return sanitizeErrorMessage(fallbackMessage);
  }

  // If already a plain string
  if (typeof errData === "string") {
    const trimmed = errData.trim();
    return sanitizeErrorMessage(trimmed || fallbackMessage);
  }

  // If standard Error object
  if (errData instanceof Error) {
    const trimmed = errData.message?.trim();
    return sanitizeErrorMessage(trimmed || fallbackMessage);
  }

  // If an array directly
  if (Array.isArray(errData)) {
    const messages = errData
      .map((item: unknown) => {
        if (typeof item === "string") return item;
        if (typeof item === "object" && item !== null) {
          const errObj = item as Record<string, unknown>;
          const locParts = Array.isArray(errObj.loc)
            ? errObj.loc.filter((part) => part !== "body")
            : [];
          const loc = locParts.join(".");
          const msg = typeof errObj.msg === "string" ? errObj.msg : "Invalid value";
          return loc ? `${loc}: ${msg}` : msg;
        }
        return null;
      })
      .filter((msg): msg is string => Boolean(msg && msg.trim()));

    if (messages.length > 0) {
      return sanitizeErrorMessage(messages.join("; "));
    }
  }

  // If an object
  if (typeof errData === "object" && errData !== null) {
    const data = errData as Record<string, unknown>;

    // 1. FastAPI Pydantic validation error array: err.detail = [...]
    if (Array.isArray(data.detail)) {
      const messages = data.detail
        .map((item: unknown) => {
          if (typeof item === "string") return item;
          if (typeof item === "object" && item !== null) {
            const errObj = item as Record<string, unknown>;
            const locParts = Array.isArray(errObj.loc)
              ? errObj.loc.filter((part) => part !== "body")
              : [];
            const loc = locParts.join(".");
            const msg = typeof errObj.msg === "string" ? errObj.msg : "Invalid value";
            return loc ? `${loc}: ${msg}` : msg;
          }
          return null;
        })
        .filter((msg): msg is string => Boolean(msg && msg.trim()));

      if (messages.length > 0) {
        return sanitizeErrorMessage(messages.join("; "));
      }
    }

    // 2. detail is a string
    if (typeof data.detail === "string" && data.detail.trim().length > 0) {
      return sanitizeErrorMessage(data.detail.trim());
    }

    // 3. detail is an object with message, error, or reason
    if (typeof data.detail === "object" && data.detail !== null) {
      const detailObj = data.detail as Record<string, unknown>;
      if (typeof detailObj.message === "string" && detailObj.message.trim().length > 0) {
        return sanitizeErrorMessage(detailObj.message.trim());
      }
      if (typeof detailObj.error === "string" && detailObj.error.trim().length > 0) {
        return sanitizeErrorMessage(detailObj.error.trim());
      }
      if (typeof detailObj.reason === "string" && detailObj.reason.trim().length > 0) {
        return sanitizeErrorMessage(detailObj.reason.trim());
      }
    }

    // 4. Top-level message or error string
    if (typeof data.message === "string" && data.message.trim().length > 0) {
      return sanitizeErrorMessage(data.message.trim());
    }
    if (typeof data.error === "string" && data.error.trim().length > 0) {
      return sanitizeErrorMessage(data.error.trim());
    }
    if (typeof data.reason === "string" && data.reason.trim().length > 0) {
      return sanitizeErrorMessage(data.reason.trim());
    }
  }

  return sanitizeErrorMessage(fallbackMessage);
}

