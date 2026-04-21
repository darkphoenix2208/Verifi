import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

interface ReasoningStep {
  step: number;
  action: string;
  tool: string;
  status: string;
  duration_ms: number;
  observation: string;
}

interface InvestigationResult {
  scenario: string;
  reasoning_steps: ReasoningStep[];
  evidence_collected: Record<string, any>[];
  final_report: string;
  risk_assessment: string;
  recommended_actions: string[];
  total_duration_ms: number;
  agent_model: string;
}

const PRESETS = [
  "Suspicious high-value transaction of $15,000 detected from a new device in a foreign country",
  "Employee EMP-1001 accessed sensitive financial records after midnight for 3 consecutive nights",
  "Ethereum wallet initiated unlimited ERC-20 token approval to an unverified smart contract",
  "Customer session shows 200 clicks per hour with rapid browser switching and 5 failed logins",
];

export function AIInvestigationDashboard() {
  const [scenario, setScenario] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<InvestigationResult | null>(null);
  const [error, setError] = useState("");

  const handleInvestigate = async () => {
    const input = scenario.trim();
    if (!input) { setError("Describe a scenario to investigate."); return; }

    setLoading(true);
    setError("");
    setResult(null);

    try {
      const res = await fetch(`${API_BASE_URL}/api/agent/investigate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scenario: input }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Investigation failed");
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  const riskColor = (level: string) => {
    switch (level?.toUpperCase()) {
      case "CRITICAL": return { text: "text-red-400", bg: "bg-red-500/15", border: "border-red-500/40" };
      case "HIGH": return { text: "text-orange-400", bg: "bg-orange-500/15", border: "border-orange-500/40" };
      case "MEDIUM": return { text: "text-amber-400", bg: "bg-amber-500/15", border: "border-amber-500/40" };
      default: return { text: "text-emerald-400", bg: "bg-emerald-500/15", border: "border-emerald-500/40" };
    }
  };

  return (
    <section className="mx-auto w-full max-w-5xl space-y-5">
      {/* Input */}
      <div className="rounded-2xl border border-zinc-800 bg-zinc-900/95 p-6 shadow-lg backdrop-blur">
        <div className="flex items-center gap-3 mb-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-violet-600 to-purple-500 shadow-lg shadow-violet-500/20">
            <svg className="h-5 w-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0112 15a9.065 9.065 0 00-6.23.693L5 14.5m14.8.8l1.402 1.402c1.232 1.232.65 3.318-1.067 3.611A48.309 48.309 0 0112 21c-2.773 0-5.491-.235-8.135-.687-1.718-.293-2.3-2.379-1.067-3.61L5 14.5" />
            </svg>
          </div>
          <div>
            <h2 className="text-lg font-bold text-zinc-100">AI Investigation Agent</h2>
            <p className="text-xs font-mono tracking-wider text-zinc-500 uppercase">Multi-Tool ReAct Pipeline</p>
          </div>
        </div>

        <textarea
          value={scenario}
          onChange={(e) => setScenario(e.target.value)}
          placeholder="Describe the suspicious activity to investigate..."
          rows={3}
          className="w-full rounded-xl border border-zinc-700 bg-zinc-950 px-4 py-3 text-sm text-zinc-100 placeholder:text-zinc-600 focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500 resize-none"
        />

        {/* Preset scenarios */}
        <div className="mt-3 flex flex-wrap gap-2">
          {PRESETS.map((p, i) => (
            <button
              key={i}
              type="button"
              onClick={() => setScenario(p)}
              className="rounded-lg border border-zinc-800 bg-zinc-950 px-3 py-1.5 text-[11px] text-zinc-400 transition hover:border-violet-500/50 hover:text-violet-300"
            >
              {p.length > 60 ? p.slice(0, 57) + "..." : p}
            </button>
          ))}
        </div>

        <button
          type="button"
          onClick={handleInvestigate}
          disabled={loading}
          className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 to-purple-500 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-violet-500/25 transition hover:shadow-violet-500/40 disabled:opacity-50 sm:w-auto"
        >
          {loading ? (
            <>
              <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" /></svg>
              Agent Investigating...
            </>
          ) : "Launch Investigation"}
        </button>

        {error && <p className="mt-3 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-2 text-sm text-red-300">{error}</p>}
      </div>

      {/* Results */}
      {result && (
        <AnimatePresence>
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-4"
          >
            {/* Risk assessment banner */}
            {(() => { const rc = riskColor(result.risk_assessment); return (
              <div className={`flex items-center justify-between rounded-2xl border ${rc.border} ${rc.bg} p-5`}>
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wider text-zinc-500">Risk Assessment</p>
                  <p className={`text-3xl font-black ${rc.text}`}>{result.risk_assessment}</p>
                </div>
                <div className="text-right">
                  <p className="text-xs text-zinc-500">Agent Model</p>
                  <p className="text-sm font-medium text-zinc-300">{result.agent_model}</p>
                  <p className="text-xs text-zinc-600 mt-1">{result.total_duration_ms}ms total</p>
                </div>
              </div>
            ); })()}

            {/* Reasoning chain */}
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/80 p-5">
              <h3 className="mb-4 text-sm font-bold uppercase tracking-wider text-zinc-400">Agent Reasoning Chain</h3>
              <div className="space-y-2">
                {result.reasoning_steps.map((step, i) => (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.1 }}
                    className="flex items-start gap-3"
                  >
                    <div className={`mt-1 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[10px] font-bold ${step.status === "success" ? "bg-emerald-500/20 text-emerald-400" : "bg-red-500/20 text-red-400"}`}>
                      {step.step}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <p className="text-sm font-semibold text-zinc-200">{step.action}</p>
                        <span className="rounded bg-zinc-800 px-1.5 py-0.5 text-[10px] font-mono text-zinc-500">{step.duration_ms}ms</span>
                      </div>
                      <p className="mt-0.5 text-xs text-zinc-500 leading-relaxed">{step.observation}</p>
                    </div>
                  </motion.div>
                ))}
              </div>
            </div>

            {/* Final report */}
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/80 p-5">
              <h3 className="mb-3 text-sm font-bold uppercase tracking-wider text-zinc-400">Investigation Report</h3>
              <div className="prose prose-sm prose-invert max-w-none text-zinc-300 leading-relaxed whitespace-pre-wrap">
                {result.final_report}
              </div>
            </div>

            {/* Recommended actions */}
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/80 p-5">
              <h3 className="mb-3 text-sm font-bold uppercase tracking-wider text-zinc-400">Recommended Actions</h3>
              <div className="space-y-2">
                {result.recommended_actions.map((action, i) => (
                  <div key={i} className="flex items-center gap-2 rounded-lg bg-zinc-950/50 px-3 py-2">
                    <svg className="h-4 w-4 shrink-0 text-violet-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <span className="text-sm text-zinc-300">{action}</span>
                  </div>
                ))}
              </div>
            </div>
          </motion.div>
        </AnimatePresence>
      )}
    </section>
  );
}
