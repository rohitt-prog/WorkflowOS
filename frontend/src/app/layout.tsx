import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "WorkFlowOS | Activity Dashboard",
  description: "Observational Event Ingestion & Workflow OS Activity Monitor",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark h-full" suppressHydrationWarning>
      <body
        className="min-h-full bg-zinc-950 text-zinc-100 antialiased selection:bg-indigo-500/20 selection:text-indigo-300"
        suppressHydrationWarning
      >
        {children}
      </body>
    </html>
  );
}
