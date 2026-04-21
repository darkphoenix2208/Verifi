import { useState } from "react";
import { CoreBankingDashboard } from "./components/dashboards/CoreBankingDashboard";
import { EmployeeRiskDashboard } from "./components/dashboards/EmployeeRiskDashboard";
import { KycVerificationPage } from "./components/kyc/KycVerificationPage";
import { DeFiSurveillanceDashboard } from "./components/defi/DeFiSurveillanceDashboard";

type ViewMode = "core-banking" | "employee-risk" | "kyc-verification" | "defi-surveillance";

const NAV_ITEMS: { key: ViewMode; label: string; icon: JSX.Element }[] = [
  {
    key: "core-banking",
    label: "Core Banking",
    icon: (
      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" />
      </svg>
    ),
  },
  {
    key: "employee-risk",
    label: "Employee Risk",
    icon: (
      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
    ),
  },
  {
    key: "kyc-verification",
    label: "KYC",
    icon: (
      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
      </svg>
    ),
  },
  {
    key: "defi-surveillance",
    label: "DeFi Radar",
    icon: (
      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9.348 14.652a3.75 3.75 0 010-5.304m5.304 0a3.75 3.75 0 010 5.304m-7.425 2.121a6.75 6.75 0 010-9.546m9.546 0a6.75 6.75 0 010 9.546M5.106 18.894c-3.808-3.807-3.808-9.98 0-13.788m13.788 0c3.808 3.808 3.808 9.981 0 13.788M12 12h.008v.008H12V12zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0z" />
      </svg>
    ),
  },
];

export default function App() {
  const [viewMode, setViewMode] = useState<ViewMode>("core-banking");

  return (
    <div className="flex min-h-screen flex-col bg-zinc-950 text-zinc-100">
      {/* ── Top accent bar ── */}
      <div className="h-[2px] w-full bg-gradient-to-r from-blue-600 via-cyan-500 to-violet-600" />

      {/* ── Header ── */}
      <header className="sticky top-0 z-40 border-b border-zinc-800/60 bg-zinc-950/80 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl flex-col gap-3 px-4 py-3 md:flex-row md:items-center md:justify-between md:px-8">
          {/* Brand */}
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-blue-600 to-cyan-500 shadow-lg shadow-blue-500/20">
              <svg className="h-5 w-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
              </svg>
            </div>
            <div>
              <h1 className="text-lg font-extrabold tracking-tight text-zinc-50">
                Verifi
              </h1>
              <p className="hidden text-[11px] font-medium tracking-wide text-zinc-500 sm:block">
                Security Console
              </p>
            </div>
          </div>

          {/* Nav tabs */}
          <nav className="flex flex-wrap items-center gap-1 rounded-xl border border-zinc-800/60 bg-zinc-900/50 p-1">
            {NAV_ITEMS.map((item) => {
              const active = viewMode === item.key;
              return (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => setViewMode(item.key)}
                  className={`inline-flex items-center gap-2 rounded-lg px-3.5 py-2 text-[13px] font-semibold transition-all duration-200 ${
                    active
                      ? "bg-gradient-to-r from-blue-600 to-blue-500 text-white shadow-md shadow-blue-500/25"
                      : "text-zinc-400 hover:bg-zinc-800/70 hover:text-zinc-200"
                  }`}
                >
                  {item.icon}
                  <span className="hidden sm:inline">{item.label}</span>
                </button>
              );
            })}
          </nav>
        </div>
      </header>

      {/* ── Page content ── */}
      <main className="flex-1 px-4 py-6 md:px-8">
        <div className="mx-auto max-w-7xl">
          {viewMode === "core-banking" ? <CoreBankingDashboard /> : null}
          {viewMode === "employee-risk" ? <EmployeeRiskDashboard /> : null}
          {viewMode === "kyc-verification" ? <KycVerificationPage /> : null}
          {viewMode === "defi-surveillance" ? <DeFiSurveillanceDashboard /> : null}
        </div>
      </main>

      {/* ── Footer ── */}
      <footer className="border-t border-zinc-800/40 py-4">
        <p className="text-center text-[11px] font-medium tracking-wide text-zinc-600">
          Verifi Security Console &middot; Built by{" "}
          <span className="text-zinc-500">darkphoenix2208</span>
        </p>
      </footer>
    </div>
  );
}
