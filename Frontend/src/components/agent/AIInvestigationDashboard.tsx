import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

const API = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

interface TraceMsg { role: string; content: string; ts: number }
interface Verdict {
  risk_level?: string; confidence?: number; summary?: string;
  key_findings?: string[]; recommended_actions?: string[];
  matched_ttps?: string[]; transaction_id?: string;
  investigation_pipeline?: string;
}
interface LGResult {
  transaction_id: string; scenario: string; route: string;
  fiat_evidence: Record<string, any>; crypto_evidence: Record<string, any>;
  rag_threat_intel: Record<string, any>; final_verdict: Verdict;
  reasoning_trace: TraceMsg[]; total_duration_ms: number; pipeline: string;
}

const PRESETS = [
  "Suspicious $15,000 transaction from a new device in a foreign country",
  "Employee EMP-1001 accessed sensitive records after midnight for 3 nights",
  "Ethereum wallet initiated unlimited ERC-20 approval to unverified contract via Tornado Cash",
  "Customer session: 200 clicks/hr, rapid browser switching, 5 failed logins",
];

const PIPELINE_NODES = [
  { id: "triage", label: "Triage", icon: "M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" },
  { id: "fiat", label: "Fiat Node", icon: "M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" },
  { id: "crypto", label: "Web3 Node", icon: "M13 10V3L4 14h7v7l9-11h-7z" },
  { id: "rag", label: "Threat Intel", icon: "M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" },
  { id: "synth", label: "CRO Synth", icon: "M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" },
];

function riskStyle(level?: string) {
  switch (level?.toUpperCase()) {
    case "CRITICAL": return { text: "text-red-400", bg: "bg-red-500/15", border: "border-red-500/40", glow: "shadow-red-500/20" };
    case "HIGH": return { text: "text-orange-400", bg: "bg-orange-500/15", border: "border-orange-500/40", glow: "shadow-orange-500/20" };
    case "MEDIUM": return { text: "text-amber-400", bg: "bg-amber-500/15", border: "border-amber-500/40", glow: "shadow-amber-500/20" };
    default: return { text: "text-emerald-400", bg: "bg-emerald-500/15", border: "border-emerald-500/40", glow: "shadow-emerald-500/20" };
  }
}

function activeNodes(route?: string): Set<string> {
  const base = new Set(["triage", "rag", "synth"]);
  if (route === "both" || route === "fiat") base.add("fiat");
  if (route === "both" || route === "crypto") base.add("crypto");
  return base;
}

/* ── Glassmorphism evidence card ────────────────────────────────── */
function EvidenceCard({ title, gradient, children }: { title: string; gradient: string; children: React.ReactNode }) {
  return (
    <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
      className="rounded-2xl border border-zinc-800 bg-zinc-900/70 backdrop-blur-md overflow-hidden">
      <div className={`h-1 w-full bg-gradient-to-r ${gradient}`} />
      <div className="p-5">
        <h4 className="mb-3 text-xs font-bold uppercase tracking-widest text-zinc-500">{title}</h4>
        {children}
      </div>
    </motion.div>
  );
}

function FindingsList({ items }: { items: string[] }) {
  if (!items?.length) return <p className="text-xs text-zinc-600 italic">No findings.</p>;
  return (
    <ul className="space-y-1.5">
      {items.map((f, i) => (
        <li key={i} className="flex items-start gap-2 text-sm text-zinc-300">
          <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-violet-400" />
          <span className="leading-snug">{f}</span>
        </li>
      ))}
    </ul>
  );
}

/* ══════════════════════════════════════════════════════════════════ */
export function AIInvestigationDashboard() {
  const [scenario, setScenario] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<LGResult | null>(null);
  const [error, setError] = useState("");

  const handleInvestigate = async () => {
    const input = scenario.trim();
    if (!input) { setError("Describe a scenario to investigate."); return; }
    setLoading(true); setError(""); setResult(null);
    try {
      const res = await fetch(`${API}/api/langgraph/investigate`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scenario: input }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Investigation failed");
      setResult(data);
    } catch (err) { setError(err instanceof Error ? err.message : "Unknown error"); }
    finally { setLoading(false); }
  };

  const active = result ? activeNodes(result.route) : new Set<string>();
  const v = result?.final_verdict;
  const rs = v ? riskStyle(v.risk_level) : riskStyle();

  return (
    <section className="mx-auto w-full max-w-6xl space-y-5">

      {/* ── Input Panel ─────────────────────────────────────────── */}
      <div className="rounded-2xl border border-zinc-800 bg-zinc-900/95 p-6 shadow-lg backdrop-blur">
        <div className="flex items-center gap-3 mb-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-violet-600 to-purple-500 shadow-lg shadow-violet-500/20">
            <svg className="h-5 w-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0112 15a9.065 9.065 0 00-6.23.693L5 14.5m14.8.8l1.402 1.402c1.232 1.232.65 3.318-1.067 3.611A48.309 48.309 0 0112 21c-2.773 0-5.491-.235-8.135-.687-1.718-.293-2.3-2.379-1.067-3.61L5 14.5" />
            </svg>
          </div>
          <div>
            <h2 className="text-lg font-bold text-zinc-100">LangGraph Investigation Orchestrator</h2>
            <p className="text-xs font-mono tracking-wider text-zinc-500 uppercase">Hierarchical Multi-Agent Pipeline</p>
          </div>
        </div>

        <textarea value={scenario} onChange={(e) => setScenario(e.target.value)}
          placeholder="Describe the suspicious activity to investigate..."
          rows={3} className="w-full rounded-xl border border-zinc-700 bg-zinc-950 px-4 py-3 text-sm text-zinc-100 placeholder:text-zinc-600 focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500 resize-none" />

        <div className="mt-3 flex flex-wrap gap-2">
          {PRESETS.map((p, i) => (
            <button key={i} type="button" onClick={() => setScenario(p)}
              className="rounded-lg border border-zinc-800 bg-zinc-950 px-3 py-1.5 text-[11px] text-zinc-400 transition hover:border-violet-500/50 hover:text-violet-300">
              {p.length > 55 ? p.slice(0, 52) + "..." : p}
            </button>
          ))}
        </div>

        <button type="button" onClick={handleInvestigate} disabled={loading}
          className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 to-purple-500 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-violet-500/25 transition hover:shadow-violet-500/40 disabled:opacity-50 sm:w-auto">
          {loading ? (<><svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" /></svg>Orchestrator Running...</>) : "Launch Investigation"}
        </button>

        {error && <p className="mt-3 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-2 text-sm text-red-300">{error}</p>}
      </div>

      {/* ── Results ──────────────────────────────────────────────── */}
      {result && (
        <AnimatePresence>
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-5">

            {/* ── Task 2: Pipeline Node Tracker ───────────────────── */}
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/80 p-5 backdrop-blur">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-xs font-bold uppercase tracking-widest text-zinc-500">Node Execution Tracker</h3>
                <span className="rounded-full bg-violet-500/10 px-3 py-1 text-[10px] font-bold uppercase tracking-wider text-violet-400">
                  Route: {result.route}
                </span>
              </div>
              <div className="flex items-center justify-between gap-1">
                {PIPELINE_NODES.map((node, idx) => {
                  const isActive = active.has(node.id);
                  const isSkipped = !isActive;
                  return (
                    <div key={node.id} className="flex items-center gap-1 flex-1 min-w-0">
                      <motion.div
                        initial={{ scale: 0.8, opacity: 0 }}
                        animate={{ scale: 1, opacity: 1 }}
                        transition={{ delay: idx * 0.15, type: "spring", stiffness: 200 }}
                        className={`flex flex-col items-center gap-1.5 rounded-xl px-2 py-3 flex-1 min-w-0 border transition-all duration-500 ${
                          isSkipped
                            ? "border-zinc-800/50 bg-zinc-950/30 opacity-30"
                            : "border-violet-500/30 bg-violet-500/5 shadow-lg shadow-violet-500/10"
                        }`}>
                        <motion.div
                          animate={isActive ? { boxShadow: ["0 0 0px rgba(139,92,246,0)", "0 0 12px rgba(139,92,246,0.5)", "0 0 0px rgba(139,92,246,0)"] } : {}}
                          transition={{ repeat: Infinity, duration: 2 }}
                          className={`flex h-8 w-8 items-center justify-center rounded-lg ${isActive ? "bg-gradient-to-br from-violet-600 to-purple-500" : "bg-zinc-800"}`}>
                          <svg className="h-4 w-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
                            <path strokeLinecap="round" strokeLinejoin="round" d={node.icon} />
                          </svg>
                        </motion.div>
                        <span className={`text-[10px] font-bold uppercase tracking-wider ${isActive ? "text-violet-300" : "text-zinc-600"}`}>{node.label}</span>
                      </motion.div>
                      {idx < PIPELINE_NODES.length - 1 && (
                        <motion.div initial={{ scaleX: 0 }} animate={{ scaleX: 1 }}
                          transition={{ delay: idx * 0.15 + 0.1 }}
                          className={`h-px w-3 shrink-0 ${isActive && active.has(PIPELINE_NODES[idx + 1]?.id) ? "bg-violet-500" : "bg-zinc-800"}`} />
                      )}
                    </div>
                  );
                })}
              </div>
            </div>

            {/* ── Task 3: Multi-Agent Evidence Grid ───────────────── */}
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {/* Fiat Node */}
              <EvidenceCard title="Fiat Node Findings" gradient="from-blue-500 to-cyan-400">
                <FindingsList items={result.fiat_evidence?.findings || []} />
                {result.fiat_evidence?.transaction_risk && (
                  <div className="mt-3 rounded-lg bg-zinc-950/60 px-3 py-2">
                    <p className="text-[10px] font-semibold uppercase text-zinc-500">TX Risk Score</p>
                    <p className="text-lg font-black text-cyan-400">{result.fiat_evidence.transaction_risk.risk_score ?? "N/A"}</p>
                    <p className="text-[10px] text-zinc-500">{result.fiat_evidence.transaction_risk.decision}</p>
                  </div>
                )}
              </EvidenceCard>

              {/* Web3 Node */}
              <EvidenceCard title="Web3 Node Findings" gradient="from-violet-500 to-purple-400">
                <FindingsList items={result.crypto_evidence?.findings || []} />
                {result.crypto_evidence?.crypto_threat && (
                  <div className="mt-3 rounded-lg bg-zinc-950/60 px-3 py-2">
                    <p className="text-[10px] font-semibold uppercase text-zinc-500">Anomaly Score</p>
                    <p className="text-lg font-black text-violet-400">{result.crypto_evidence.crypto_threat.anomaly_score ?? "N/A"}</p>
                    <p className="text-[10px] text-zinc-500">{result.crypto_evidence.crypto_threat.is_anomaly ? "ANOMALOUS" : "Normal"}</p>
                  </div>
                )}
              </EvidenceCard>

              {/* Threat Intel RAG */}
              <EvidenceCard title="Threat Intel (RAG)" gradient="from-orange-500 to-amber-400">
                <p className="mb-2 text-[10px] text-zinc-500">{result.rag_threat_intel?.coverage}</p>
                {(result.rag_threat_intel?.matched_vectors || []).length > 0 ? (
                  <div className="space-y-2">
                    {result.rag_threat_intel.matched_vectors.map((vec: any, i: number) => (
                      <div key={i} className="rounded-lg bg-zinc-950/60 px-3 py-2">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-semibold text-zinc-200">{vec.vector_id?.replace(/_/g, " ")}</span>
                          <span className={`rounded px-1.5 py-0.5 text-[9px] font-bold uppercase ${
                            vec.severity === "CRITICAL" ? "bg-red-500/20 text-red-400" : "bg-orange-500/20 text-orange-400"
                          }`}>{vec.severity}</span>
                        </div>
                        <p className="mt-1 text-[11px] text-zinc-400 leading-snug">{vec.description}</p>
                        {vec.ttps?.length > 0 && (
                          <div className="mt-1.5 flex flex-wrap gap-1">
                            {vec.ttps.map((t: string, j: number) => (
                              <span key={j} className="rounded bg-zinc-800 px-1.5 py-0.5 text-[9px] font-mono text-amber-400">{t.split(" — ")[0]}</span>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                ) : <p className="text-xs text-zinc-600 italic">No matching attack vectors.</p>}
              </EvidenceCard>
            </div>

            {/* ── Reasoning Trace ─────────────────────────────────── */}
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/80 p-5 backdrop-blur">
              <h3 className="mb-3 text-xs font-bold uppercase tracking-widest text-zinc-500">Reasoning Trace ({result.reasoning_trace?.length || 0} messages)</h3>
              <div className="space-y-1.5 max-h-48 overflow-y-auto pr-2 custom-scrollbar">
                {(result.reasoning_trace || []).map((msg, i) => (
                  <motion.div key={i} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.05 }}
                    className="flex items-start gap-2">
                    <span className={`mt-0.5 shrink-0 rounded px-1.5 py-0.5 text-[9px] font-bold uppercase ${
                      msg.role === "system" ? "bg-zinc-800 text-zinc-500" :
                      msg.role === "triage" ? "bg-violet-500/20 text-violet-400" :
                      msg.role === "synthesizer" ? "bg-emerald-500/20 text-emerald-400" :
                      "bg-blue-500/20 text-blue-400"
                    }`}>{msg.role}</span>
                    <span className="text-xs text-zinc-400 leading-snug">{msg.content}</span>
                  </motion.div>
                ))}
              </div>
            </div>

            {/* ── Task 4: Final SAR (Suspicious Activity Report) ─── */}
            {v && (
              <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}
                className={`rounded-2xl border-2 ${rs.border} ${rs.bg} p-6 shadow-xl ${rs.glow} backdrop-blur`}>
                {/* Header */}
                <div className="flex items-start justify-between border-b border-zinc-700/50 pb-4 mb-4">
                  <div>
                    <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-zinc-500">Suspicious Activity Report</p>
                    <p className="text-[10px] font-mono text-zinc-600 mt-0.5">ID: {v.transaction_id} | Pipeline: {v.investigation_pipeline}</p>
                  </div>
                  <div className="text-right">
                    <p className={`text-3xl font-black ${rs.text}`}>{v.risk_level || "UNKNOWN"}</p>
                    {v.confidence != null && (
                      <div className="mt-1 flex items-center gap-2 justify-end">
                        <div className="h-1.5 w-20 rounded-full bg-zinc-800 overflow-hidden">
                          <motion.div initial={{ width: 0 }} animate={{ width: `${(v.confidence * 100)}%` }}
                            transition={{ delay: 0.5, duration: 0.8 }}
                            className={`h-full rounded-full bg-gradient-to-r ${
                              v.risk_level === "CRITICAL" ? "from-red-600 to-red-400" :
                              v.risk_level === "HIGH" ? "from-orange-600 to-orange-400" :
                              "from-emerald-600 to-emerald-400"
                            }`} />
                        </div>
                        <span className="text-xs font-bold text-zinc-400">{(v.confidence * 100).toFixed(0)}%</span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Summary */}
                {v.summary && <p className="text-sm text-zinc-300 leading-relaxed mb-4">{v.summary}</p>}

                {/* Key Findings + Actions side by side */}
                <div className="grid gap-4 md:grid-cols-2">
                  <div>
                    <h4 className="mb-2 text-[10px] font-bold uppercase tracking-widest text-zinc-500">Key Findings</h4>
                    <FindingsList items={v.key_findings || []} />
                  </div>
                  <div>
                    <h4 className="mb-2 text-[10px] font-bold uppercase tracking-widest text-zinc-500">Recommended Actions</h4>
                    <ul className="space-y-1.5">
                      {(v.recommended_actions || []).map((a, i) => (
                        <li key={i} className="flex items-start gap-2 text-sm text-zinc-300">
                          <svg className="mt-0.5 h-3.5 w-3.5 shrink-0 text-violet-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                          </svg>
                          <span className="leading-snug">{a}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>

                {/* Matched TTPs */}
                {(v.matched_ttps?.length ?? 0) > 0 && (
                  <div className="mt-4 pt-3 border-t border-zinc-700/50">
                    <h4 className="mb-2 text-[10px] font-bold uppercase tracking-widest text-zinc-500">Matched MITRE ATT&CK TTPs</h4>
                    <div className="flex flex-wrap gap-1.5">
                      {v.matched_ttps!.map((t, i) => (
                        <span key={i} className="rounded-md border border-red-500/20 bg-red-500/10 px-2 py-1 text-[10px] font-mono text-red-400">{t}</span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Footer */}
                <div className="mt-4 pt-3 border-t border-zinc-700/50 flex items-center justify-between">
                  <p className="text-[10px] text-zinc-600">Generated by Verifi Security Console</p>
                  <p className="text-[10px] font-mono text-zinc-600">{result.total_duration_ms}ms | {result.pipeline}</p>
                </div>
              </motion.div>
            )}

          </motion.div>
        </AnimatePresence>
      )}
    </section>
  );
}
