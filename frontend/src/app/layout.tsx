import type { Metadata } from "next";
import "./globals.css";
import { ThemeProvider } from "@/lib/theme";

export const metadata: Metadata = {
  title: "WorkFlowOS | Intelligent Workflow Automation",
  description:
    "WorkFlowOS — Observational desktop activity agent, workflow discovery, AI proposal generation, and local, safety-first workflow automation engine.",
  keywords: ["workflow", "automation", "AI", "macOS", "desktop agent"],
};

// Inline blocking script executed before paint to eliminate any theme flash (FOUC)
const themeInitializerScript = `(function(){try{var t=localStorage.getItem("workflowos_theme");var d=window.matchMedia("(prefers-color-scheme: dark)").matches;if(t==="dark"||(!t&&d)||(t==="system"&&d)){document.documentElement.classList.add("dark");document.documentElement.classList.remove("light");document.documentElement.setAttribute("data-theme","dark");document.documentElement.style.colorScheme="dark";}else{document.documentElement.classList.remove("dark");document.documentElement.classList.add("light");document.documentElement.setAttribute("data-theme","light");document.documentElement.style.colorScheme="light";}}catch(e){}})();`;

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="h-full" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: themeInitializerScript,
          }}
        />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        {/* eslint-disable-next-line @next/next/no-page-custom-font */}
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap"
          rel="stylesheet"
        />
      </head>
      <body
        className="h-full bg-[#F7F9FC] text-[#475569] dark:bg-[#0B0F17] dark:text-[#94A3B8] antialiased selection:bg-[#DBEAFE] selection:text-[#1D4ED8] dark:selection:bg-[#1E293B] dark:selection:text-[#60A5FA]"
        suppressHydrationWarning
      >
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}
