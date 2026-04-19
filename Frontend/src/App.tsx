import { useState } from "react";
import { CoreBankingDashboard } from "./components/dashboards/CoreBankingDashboard";
import { EmployeeRiskDashboard } from "./components/dashboards/EmployeeRiskDashboard";
import { KycVerificationPage } from "./components/kyc/KycVerificationPage";

type ViewMode = "core-banking" | "employee-risk" | "kyc-verification";

export default function App() {
  const [viewMode, setViewMode] = useState<ViewMode>("core-banking");

  return (
    <main className="min-h-screen bg-zinc-950 px-4 py-6 text-zinc-100 md:px-8">
      <div className="mx-auto max-w-7xl">
        <header className="mb-6 rounded-2xl border border-zinc-800 bg-zinc-900/90 p-4 backdrop-blur">
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div>
              <h1 className="text-2xl font-bold text-zinc-100">Verifi Security Console</h1>
              <p className="mt-1 text-sm text-zinc-400">
                End-to-end monitoring for transaction fraud and insider risk analytics.
              </p>
            </div>

            <nav className="inline-flex rounded-xl border border-zinc-700 bg-zinc-950 p-1">
              <button
                type="button"
                onClick={() => setViewMode("core-banking")}
                className={`rounded-lg px-4 py-2 text-sm font-medium transition ${
                  viewMode === "core-banking"
                    ? "bg-blue-600 text-white"
                    : "text-zinc-300 hover:bg-zinc-800"
                }`}
              >
                Core Banking
              </button>
              <button
                type="button"
                onClick={() => setViewMode("employee-risk")}
                className={`rounded-lg px-4 py-2 text-sm font-medium transition ${
                  viewMode === "employee-risk"
                    ? "bg-blue-600 text-white"
                    : "text-zinc-300 hover:bg-zinc-800"
                }`}
              >
                Employee Risk
              </button>
              <button
                type="button"
                onClick={() => setViewMode("kyc-verification")}
                className={`rounded-lg px-4 py-2 text-sm font-medium transition ${
                  viewMode === "kyc-verification"
                    ? "bg-blue-600 text-white"
                    : "text-zinc-300 hover:bg-zinc-800"
                }`}
              >
                KYC Verification
              </button>
            </nav>
          </div>
        </header>

        {viewMode === "core-banking" ? <CoreBankingDashboard /> : null}
        {viewMode === "employee-risk" ? <EmployeeRiskDashboard /> : null}
        {viewMode === "kyc-verification" ? <KycVerificationPage /> : null}
      </div>
    </main>
  );
}
