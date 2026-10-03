import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "WorkFlowOS | Intelligent Workflow Automation",
  description:
    "WorkFlowOS — Observational desktop activity agent, workflow discovery, AI proposal generation, and production-grade workflow automation engine.",
  keywords: ["workflow", "automation", "AI", "macOS", "desktop agent"],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="h-full" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        {/* eslint-disable-next-line @next/next/no-page-custom-font */}
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap"
          rel="stylesheet"
        />
      </head>
      <body
        className="h-full bg-[#F7F9FC] text-[#475569] antialiased selection:bg-[#DBEAFE] selection:text-[#1D4ED8]"
        suppressHydrationWarning
      >
        {children}
      </body>
    </html>
  );
}
