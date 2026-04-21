import { useState } from "react";

interface CryptoRiskReport {
  transaction_hash: string;
  from?: string;
  to?: string;
  value_eth: number;
  risk_score: number;
  risk_level: string;
  flags: string[];
  gas_used?: number;
  block_number?: number;
  status?: string;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export function DeFiSurveillanceDashboard() {
  const [txHash, setTxHash] = useState("");
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState<CryptoRiskReport | null>(null);
  const [error, setError] = useState<string>("");

  const handleScan = async () => {
    if (!txHash.trim()) {
      setError("Please enter a transaction hash.");
      return;
    }

    setLoading(true);
    setError("");
    setReport(null);

    try {
      const response = await fetch(`${API_BASE_URL}/api/crypto/analyze/${txHash.trim()}`);
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Failed to analyze transaction.");
      }

      setReport(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "An unknown error occurred.");
    } finally {
      setLoading(false);
    }
  };

  const getRiskColorClass = (level: string) => {
    switch (level.toUpperCase()) {
      case "CRITICAL":
        return "text-red-500";
      case "WARNING":
        return "text-yellow-500";
      case "SAFE":
        return "text-emerald-500";
      default:
        return "text-zinc-500";
    }
  };

  const getRiskBgClass = (level: string) => {
    switch (level.toUpperCase()) {
      case "CRITICAL":
        return "bg-red-500/10 border-red-500/30";
      case "WARNING":
        return "bg-yellow-500/10 border-yellow-500/30";
      case "SAFE":
        return "bg-emerald-500/10 border-emerald-500/30";
      default:
        return "bg-zinc-500/10 border-zinc-500/30";
    }
  };

  return (
    <section className="mx-auto w-full max-w-4xl space-y-6">
      {/* Search Header */}
      <div className="rounded-2xl border border-zinc-800 bg-zinc-900 p-6 shadow-lg">
        <h2 className="mb-4 text-xl font-bold text-zinc-100">DeFi & Crypto Surveillance</h2>
        <p className="mb-6 text-sm text-zinc-400">
          Enter an Ethereum transaction hash to perform a real-time risk analysis. Our engine checks for mixer interactions, massive whale transfers, and suspicious contract creations.
        </p>

        <div className="flex flex-col gap-3 sm:flex-row">
          <input
            type="text"
            placeholder="0x..."
            value={txHash}
            onChange={(e) => setTxHash(e.target.value)}
            className="flex-1 rounded-xl border border-zinc-700 bg-zinc-950 px-4 py-3 text-sm text-zinc-100 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            onKeyDown={(e) => e.key === "Enter" && handleScan()}
          />
          <button
            type="button"
            onClick={handleScan}
            disabled={loading}
            className="inline-flex items-center justify-center rounded-xl bg-blue-600 px-6 py-3 text-sm font-semibold text-white transition hover:bg-blue-500 disabled:opacity-50"
          >
            {loading ? (
              <>
                <svg className="mr-2 h-4 w-4 animate-spin text-white" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Scanning...
              </>
            ) : (
              "Scan Transaction"
            )}
          </button>
        </div>

        {error && (
          <div className="mt-4 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
            {error}
          </div>
        )}
      </div>

      {/* Results UI */}
      {report && (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
          <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
            {/* Massive Risk Indicator */}
            <div className={`col-span-1 flex flex-col items-center justify-center rounded-2xl border p-8 text-center shadow-lg ${getRiskBgClass(report.risk_level)}`}>
              <p className="text-sm font-semibold tracking-wider text-zinc-400 uppercase">Risk Score</p>
              <h3 className={`mt-2 text-7xl font-black tracking-tighter ${getRiskColorClass(report.risk_level)}`}>
                {report.risk_score}
              </h3>
              <div className={`mt-4 inline-flex items-center rounded-full px-4 py-1.5 text-sm font-bold uppercase tracking-widest ${getRiskBgClass(report.risk_level)} ${getRiskColorClass(report.risk_level)}`}>
                {report.risk_level}
              </div>
            </div>

            {/* Base Transaction Details */}
            <div className="col-span-1 md:col-span-2 rounded-2xl border border-zinc-800 bg-zinc-900 p-6 shadow-lg">
              <h3 className="mb-4 text-lg font-semibold text-zinc-100">Transaction Details</h3>
              <div className="space-y-4">
                <div>
                  <p className="text-xs font-semibold text-zinc-500 uppercase">Transaction Hash</p>
                  <p className="mt-1 break-all text-sm font-mono text-zinc-300">{report.transaction_hash}</p>
                </div>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <div>
                    <p className="text-xs font-semibold text-zinc-500 uppercase">From</p>
                    <p className="mt-1 break-all text-sm font-mono text-zinc-300">{report.from || "N/A"}</p>
                  </div>
                  <div>
                    <p className="text-xs font-semibold text-zinc-500 uppercase">To</p>
                    <p className="mt-1 break-all text-sm font-mono text-zinc-300">{report.to || "Contract Deployment"}</p>
                  </div>
                </div>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                  <div>
                    <p className="text-xs font-semibold text-zinc-500 uppercase">Value</p>
                    <p className="mt-1 text-lg font-medium text-zinc-100">{report.value_eth} <span className="text-sm text-zinc-400">ETH</span></p>
                  </div>
                  {report.block_number && (
                    <div>
                      <p className="text-xs font-semibold text-zinc-500 uppercase">Block</p>
                      <p className="mt-1 text-sm text-zinc-300">{report.block_number}</p>
                    </div>
                  )}
                  {report.status && (
                    <div>
                      <p className="text-xs font-semibold text-zinc-500 uppercase">Status</p>
                      <p className={`mt-1 text-sm font-medium ${report.status === 'success' ? 'text-emerald-400' : 'text-red-400'}`}>
                        {report.status.toUpperCase()}
                      </p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Flags List */}
          {report.flags && report.flags.length > 0 && (
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900 p-6 shadow-lg">
              <h3 className="mb-4 text-lg font-semibold text-zinc-100">Identified Risk Factors</h3>
              <ul className="space-y-3">
                {report.flags.map((flag, idx) => {
                  const [title, description] = flag.includes(': ') ? flag.split(': ') : ['FLAG', flag];
                  return (
                    <li key={idx} className="flex items-start gap-3 rounded-xl border border-zinc-800/50 bg-zinc-950/50 p-4">
                      <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-red-500/20 text-red-500">
                        <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                        </svg>
                      </div>
                      <div>
                        <p className="text-sm font-semibold tracking-wide text-zinc-200">{title}</p>
                        <p className="mt-1 text-sm text-zinc-400">{description}</p>
                      </div>
                    </li>
                  )
                })}
              </ul>
            </div>
          )}
          
          {report.flags && report.flags.length === 0 && (
            <div className="flex items-center gap-3 rounded-2xl border border-emerald-500/20 bg-emerald-500/5 p-6 text-emerald-400 shadow-lg">
              <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <p className="font-medium tracking-wide">No suspicious flags detected for this transaction.</p>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
