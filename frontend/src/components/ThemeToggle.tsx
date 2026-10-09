"use client";

import React from "react";
import { useTheme } from "@/lib/theme";

interface ThemeToggleProps {
  className?: string;
  showLabel?: boolean;
}

export default function ThemeToggle({
  className = "",
  showLabel = false,
}: ThemeToggleProps) {
  const { theme, resolvedTheme, toggleTheme, mounted } = useTheme();

  // Until mounted on client, render a neutral button skeleton to prevent hydration mismatch
  if (!mounted) {
    return (
      <button
        type="button"
        disabled
        aria-label="Theme toggle loading"
        className={`flex items-center gap-2 px-2.5 py-1.5 text-xs font-medium rounded-lg bg-white dark:bg-[#111827] border border-[#E2E8F0] dark:border-[#1E293B] text-[#94A3B8] shadow-2xs opacity-75 cursor-default ${className}`}
      >
        <span className="w-3.5 h-3.5 rounded-full bg-slate-200 dark:bg-slate-700 animate-pulse" />
        {showLabel && <span className="text-[11px]">Theme</span>}
      </button>
    );
  }

  const isDark = resolvedTheme === "dark";

  return (
    <button
      type="button"
      onClick={toggleTheme}
      aria-label={
        isDark
          ? `Current theme: dark (${theme}). Click to switch to light mode.`
          : `Current theme: light (${theme}). Click to switch to dark mode.`
      }
      title={
        isDark
          ? `Current theme: Dark (${theme === "system" ? "System" : "Manual"})\nClick to switch to Light mode`
          : `Current theme: Light (${theme === "system" ? "System" : "Manual"})\nClick to switch to Dark mode`
      }
      className={`group relative flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium rounded-lg border border-[#E2E8F0] dark:border-[#1E293B] bg-white dark:bg-[#111827] text-[#0F172A] dark:text-[#F8FAFC] hover:bg-[#F8FAFC] dark:hover:bg-[#162035] hover:border-[#CBD5E1] dark:hover:border-[#334155] shadow-2xs transition-all duration-150 active:translate-y-px cursor-pointer focus:outline-hidden focus-visible:ring-2 focus-visible:ring-[#2563EB]/40 dark:focus-visible:ring-[#3B82F6]/50 ${className}`}
    >
      {isDark ? (
        // Moon Icon (Dark Mode active, clicking switches to Light)
        <svg
          className="w-3.5 h-3.5 text-amber-400 group-hover:rotate-12 transition-transform duration-200 shrink-0"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"
          />
        </svg>
      ) : (
        // Sun Icon (Light Mode active, clicking switches to Dark)
        <svg
          className="w-3.5 h-3.5 text-amber-500 group-hover:rotate-45 transition-transform duration-200 shrink-0"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"
          />
        </svg>
      )}

      {showLabel ? (
        <span className="text-[11px] font-medium capitalize">
          {theme === "system" ? "Auto" : theme}
        </span>
      ) : (
        <span className="hidden xl:inline text-[11px] font-medium text-[#64748B] dark:text-[#94A3B8]">
          {isDark ? "Dark" : "Light"}
        </span>
      )}
    </button>
  );
}
