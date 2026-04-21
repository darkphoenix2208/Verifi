import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  getCryptoRadarWsUrl,
  getCryptoRadarDemoWsUrl,
} from "../../services/wsService";

/* ------------------------------------------------------------------ */
/* Types                                                               */
/* ------------------------------------------------------------------ */
interface CryptoThreatReport {
  transaction_hash: string;
  id?: string;
  from?: string;
  to?: string;
  value_eth: number;
  risk_score: number;
  risk_level: string;
  flags: string[];
  gas_used?: number;
  block_number?: number;
  status?: string;
  contract_name?: string | null;
  error?: string;
}

type RadarMode = "demo" | "live";
type ConnectionStatus = "connecting" | "connected" | "disconnected" | "error";

const MAX_THREATS = 50;

/* ------------------------------------------------------------------ */
/* Component                                                           */
/* ------------------------------------------------------------------ */
export function DeFiSurveillanceDashboard() {
  const [mode, setMode] = useState<RadarMode>("demo");
  const [liveThreats, setLiveThreats] = useState<CryptoThreatReport[]>([]);
  const [connectionStatus, setConnectionStatus] =
    useState<ConnectionStatus>("connecting");
  const [threatCount, setThreatCount] = useState(0);

  const socketRef = useRef<WebSocket | null>(null);
  const retryRef = useRef<number | null>(null);

  /* WebSocket lifecycle -------------------------------------------- */
  useEffect(() => {
    let unmounted = false;

    // Clear previous threats on mode switch
    setLiveThreats([]);
    setThreatCount(0);

    const connect = () => {
      if (unmounted) return;
      setConnectionStatus("connecting");

      const wsUrl =
        mode === "demo" ? getCryptoRadarDemoWsUrl() : getCryptoRadarWsUrl();
      const socket = new WebSocket(wsUrl);
      socketRef.current = socket;

      socket.onopen = () => {
        if (unmounted) return;
        setConnectionStatus("connected");
      };

      socket.onerror = () => {
        if (unmounted) return;
        setConnectionStatus("error");
      };

      socket.onmessage = (event) => {
        if (unmounted) return;
        try {
          const report = JSON.parse(event.data) as CryptoThreatReport;
          if (report.error) return; // skip error frames
          if (!report.id) report.id = crypto.randomUUID(); // Stable key for animations
          setLiveThreats((prev) => [report, ...prev].slice(0, MAX_THREATS));
          setThreatCount((c) => c + 1);
        } catch {
          // malformed payload — ignore
        }
      };

      socket.onclose = () => {
        if (unmounted) return;
        setConnectionStatus("disconnected");
        retryRef.current = window.setTimeout(connect, 2500);
      };
    };

    connect();

    return () => {
      unmounted = true;
      if (retryRef.current) window.clearTimeout(retryRef.current);
      if (socketRef.current) socketRef.current.close();
    };
  }, [mode]);

  /* Helpers -------------------------------------------------------- */
  const riskColor = (level: string) => {
    switch (level.toUpperCase()) {
      case "CRITICAL":
        return { text: "text-red-400", bg: "bg-red-500/15", border: "border-red-500/40", glow: "shadow-red-500/20" };
      case "WARNING":
        return { text: "text-amber-400", bg: "bg-amber-500/15", border: "border-amber-500/40", glow: "shadow-amber-500/20" };
      default:
        return { text: "text-zinc-400", bg: "bg-zinc-500/15", border: "border-zinc-500/40", glow: "shadow-zinc-500/10" };
    }
  };

  const shortenAddr = (addr?: string): string => {
    if (!addr) return "N/A";
    if (addr.length <= 14) return addr;
    return `${addr.slice(0, 6)}...${addr.slice(-4)}`;
  };

  const statusDot =
    connectionStatus === "connected"
      ? "bg-emerald-400"
      : connectionStatus === "connecting"
        ? "bg-blue-400"
        : connectionStatus === "error"
          ? "bg-red-400"
          : "bg-zinc-500";

  const statusLabel =
    connectionStatus === "connected"
      ? mode === "demo"
        ? "DEMO: Streaming Simulated Threats"
        : "LIVE: Scanning Ethereum Mempool"
      : connectionStatus === "connecting"
        ? "CONNECTING..."
        : connectionStatus === "error"
          ? "CONNECTION ERROR"
          : "RECONNECTING...";

  /* Render --------------------------------------------------------- */
  return (
    <section className="mx-auto w-full max-w-5xl space-y-5">
      {/* ── Radar Header ── */}
      <div className="rounded-2xl border border-zinc-800 bg-zinc-900/95 p-5 shadow-lg backdrop-blur">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          {/* Left: status */}
          <div className="flex items-center gap-3">
            <span className="relative flex h-3 w-3">
              <span
                className={`absolute inline-flex h-full w-full animate-ping rounded-full opacity-75 ${statusDot}`}
              />
              <span
                className={`relative inline-flex h-3 w-3 rounded-full ${statusDot}`}
              />
            </span>
            <div>
              <h2 className="text-lg font-bold tracking-wide text-zinc-100">
                DeFi Threat Radar
              </h2>
              <p className="text-xs font-mono tracking-widest text-zinc-400 uppercase">
                {statusLabel}
              </p>
            </div>
          </div>

          {/* Right: mode toggle + counters */}
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 rounded-full border border-zinc-700 bg-zinc-950 p-1">
              <button
                type="button"
                onClick={() => setMode("demo")}
                className={`rounded-full px-4 py-1.5 text-xs font-semibold transition ${
                  mode === "demo"
                    ? "bg-cyan-600 text-white shadow-lg shadow-cyan-500/30"
                    : "text-zinc-400 hover:text-zinc-200"
                }`}
              >
                Demo Mode
              </button>
              <button
                type="button"
                onClick={() => setMode("live")}
                className={`rounded-full px-4 py-1.5 text-xs font-semibold transition ${
                  mode === "live"
                    ? "bg-red-600 text-white shadow-lg shadow-red-500/30"
                    : "text-zinc-400 hover:text-zinc-200"
                }`}
              >
                Live Mode
              </button>
            </div>

            <div className="hidden items-center gap-3 md:flex">
              <div className="rounded-lg border border-zinc-800 bg-zinc-950 px-3 py-1.5 text-center">
                <p className="text-[10px] font-semibold tracking-wider text-zinc-500 uppercase">
                  Threats
                </p>
                <p className="text-lg font-bold font-mono text-red-400">
                  {threatCount}
                </p>
              </div>
              <div className="rounded-lg border border-zinc-800 bg-zinc-950 px-3 py-1.5 text-center">
                <p className="text-[10px] font-semibold tracking-wider text-zinc-500 uppercase">
                  Buffer
                </p>
                <p className="text-lg font-bold font-mono text-zinc-300">
                  {liveThreats.length}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── Scanline Overlay + Threat Feed ── */}
      <div className="relative min-h-[420px] rounded-2xl border border-zinc-800 bg-zinc-950/80 p-4 shadow-inner overflow-hidden">
        {/* Decorative scanline */}
        <div
          className="pointer-events-none absolute inset-0 z-10 opacity-[0.03]"
          style={{
            backgroundImage:
              "repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(255,255,255,0.04) 2px, rgba(255,255,255,0.04) 4px)",
          }}
        />

        {/* Empty state */}
        {liveThreats.length === 0 && (
          <div className="flex h-80 items-center justify-center">
            <div className="text-center">
              <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full border border-zinc-800 bg-zinc-900">
                <svg
                  className="h-7 w-7 animate-pulse text-cyan-500"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={1.5}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M9.348 14.652a3.75 3.75 0 010-5.304m5.304 0a3.75 3.75 0 010 5.304m-7.425 2.121a6.75 6.75 0 010-9.546m9.546 0a6.75 6.75 0 010 9.546M5.106 18.894c-3.808-3.807-3.808-9.98 0-13.788m13.788 0c3.808 3.808 3.808 9.981 0 13.788M12 12h.008v.008H12V12zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0z"
                  />
                </svg>
              </div>
              <p className="text-sm font-medium text-zinc-400">
                Awaiting incoming threat signals...
              </p>
              <p className="mt-1 text-xs text-zinc-600">
                {mode === "demo"
                  ? "Demo threats arrive every 3 seconds"
                  : "Monitoring Ethereum mempool for suspicious activity"}
              </p>
            </div>
          </div>
        )}

        {/* Threat cards */}
        <div className="relative z-20 space-y-4">
          <AnimatePresence initial={false}>
            {liveThreats.map((threat) => {
              const rc = riskColor(threat.risk_level);
              return (
                <motion.div
                  layout
                  key={threat.id}
                  initial={{ opacity: 0, y: -40, scale: 0.97 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.95 }}
                  transition={{ type: "spring", stiffness: 350, damping: 28 }}
                  className={`rounded-2xl border ${rc.border} bg-zinc-900/80 shadow-lg ${rc.glow} backdrop-blur-sm overflow-hidden`}
                >
                  {/* ── Card top accent ── */}
                  <div className={`h-1 w-full ${threat.risk_level === "CRITICAL" ? "bg-gradient-to-r from-red-600 to-orange-500" : "bg-gradient-to-r from-amber-500 to-yellow-400"}`} />

                  <div className="p-5">
                    {/* ── Row 1: Risk badge + Target name + Meta ── */}
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                      <div className="flex items-center gap-4">
                        {/* Risk score circle */}
                        <div
                          className={`flex h-14 w-14 shrink-0 items-center justify-center rounded-xl border-2 ${rc.border} font-mono text-2xl font-black ${rc.text}`}
                        >
                          {threat.risk_score}
                        </div>
                        <div>
                          <p className="text-base font-bold text-zinc-50">
                            {threat.contract_name
                              ? `Target: ${threat.contract_name}`
                              : threat.to
                                ? "Unknown Contract"
                                : "Contract Deployment"}
                          </p>
                          <div className="mt-1 flex items-center gap-2">
                            <span
                              className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider ${
                                threat.risk_level === "CRITICAL"
                                  ? "bg-red-500/20 text-red-400 ring-1 ring-red-500/30"
                                  : "bg-amber-500/20 text-amber-400 ring-1 ring-amber-500/30"
                              }`}
                            >
                              {threat.risk_level}
                            </span>
                            {threat.block_number && (
                              <span className="text-[11px] font-mono text-zinc-500">
                                Block #{threat.block_number}
                              </span>
                            )}
                          </div>
                        </div>
                      </div>

                      {threat.value_eth > 0 && (
                        <div className="rounded-lg border border-zinc-700/50 bg-zinc-950/60 px-3 py-2 text-right">
                          <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">Value</p>
                          <p className="text-lg font-bold font-mono text-zinc-100">
                            {threat.value_eth} <span className="text-sm text-zinc-500">ETH</span>
                          </p>
                        </div>
                      )}
                    </div>

                    {/* ── Row 2: Addresses ── */}
                    <div className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2">
                      <div className="rounded-lg bg-zinc-950/50 px-3 py-2">
                        <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-600">From</p>
                        <p className="mt-0.5 font-mono text-xs text-zinc-400">
                          {shortenAddr(threat.from)}
                        </p>
                      </div>
                      <div className="rounded-lg bg-zinc-950/50 px-3 py-2">
                        <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-600">To</p>
                        <p className="mt-0.5 font-mono text-xs text-zinc-400">
                          {threat.to ? shortenAddr(threat.to) : "Contract Creation"}
                        </p>
                      </div>
                    </div>

                    {/* ── Row 3: Flags as clean list ── */}
                    {threat.flags.length > 0 && (
                      <div className="mt-4 space-y-1.5">
                        {threat.flags.map((flag, fi) => {
                          const isCritical =
                            flag.startsWith("CRITICAL") ||
                            flag.startsWith("MIXER");
                          return (
                            <div
                              key={fi}
                              className={`flex items-start gap-2.5 rounded-lg px-3 py-2 text-xs ${
                                isCritical
                                  ? "bg-red-500/10 text-red-300"
                                  : "bg-amber-500/8 text-amber-300"
                              }`}
                            >
                              <svg
                                className={`mt-0.5 h-3.5 w-3.5 shrink-0 ${isCritical ? "text-red-400" : "text-amber-400"}`}
                                fill="none"
                                viewBox="0 0 24 24"
                                stroke="currentColor"
                                strokeWidth={2}
                              >
                                <path
                                  strokeLinecap="round"
                                  strokeLinejoin="round"
                                  d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                                />
                              </svg>
                              <span className="leading-snug">{flag}</span>
                            </div>
                          );
                        })}
                      </div>
                    )}

                    {/* ── Tx hash footer ── */}
                    <p className="mt-3 font-mono text-[10px] text-zinc-600">
                      TX {threat.transaction_hash}
                    </p>
                  </div>
                </motion.div>
              );
            })}
          </AnimatePresence>
        </div>
      </div>
    </section>
  );
}
