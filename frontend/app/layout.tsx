import type { Metadata } from "next";
import "./globals.css";
import Link from "next/link";

export const metadata: Metadata = {
  title: "FedLens — FOMC Intelligence System",
  description: "Evidence-grounded monetary policy intelligence. Track Fed stance, detect narrative divergences, and analyze statement changes.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <div className="app-shell">
          <header className="topbar">
            <Link href="/" className="topbar-logo">
              <span className="topbar-logo-mark">FL</span>
              FEDLENS
            </Link>
            <nav className="topbar-nav">
              <Link href="/">Dashboard</Link>
              <Link href="/divergences">Divergences</Link>
            </nav>
            <div className="topbar-status">
              <div className="status-dot" />
              API LIVE · localhost:8000
            </div>
          </header>
          <main className="main-content">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
