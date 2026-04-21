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
        <div className="relative z-20 space-y-3">
          <AnimatePresence initial={false}>
            {liveThreats.map((threat, idx) => {
              const rc = riskColor(threat.risk_level);
              return (
                <motion.div
                  layout
                  key={threat.id}
                  initial={{ opacity: 0, y: -40, scale: 0.97 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.95 }}
                  transition={{ type: "spring", stiffness: 350, damping: 28 }}
                  className={`rounded-xl border ${rc.border} ${rc.bg} p-4 shadow-lg ${rc.glow} backdrop-blur-sm`}
                >
                  {/* Card header */}
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                    <div className="flex items-center gap-3">
                      {/* Risk badge */}
                      <div
                        className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-lg border ${rc.border} ${rc.bg} font-mono text-xl font-black ${rc.text}`}
                      >
                        {threat.risk_score}
                      </div>
                      <div>
                        {/* Contract name */}
                        <p className="text-sm font-bold text-zinc-100">
                          {threat.contract_name
                            ? `Target: ${threat.contract_name}`
                            : threat.to
                              ? "Unknown Contract"
                              : "Contract Deployment"}
                        </p>
                        <p
                          className={`text-xs font-semibold uppercase tracking-widest ${rc.text}`}
                        >
                          {threat.risk_level}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-3 text-xs text-zinc-400">
                      {threat.value_eth > 0 && (
                        <span className="rounded-md border border-zinc-700 bg-zinc-900 px-2 py-1 font-mono font-medium text-zinc-200">
                          {threat.value_eth} ETH
                        </span>
                      )}
                      {threat.block_number && (
                        <span className="font-mono">
                          Block #{threat.block_number}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Addresses */}
                  <div className="mt-3 grid grid-cols-1 gap-1 sm:grid-cols-2">
                    <p className="truncate text-xs text-zinc-500">
                      <span className="text-zinc-600">FROM </span>
                      <span className="font-mono text-zinc-400">
                        {threat.from || "N/A"}
                      </span>
                    </p>
                    <p className="truncate text-xs text-zinc-500">
                      <span className="text-zinc-600">TO </span>
                      <span className="font-mono text-zinc-400">
                        {threat.to || "Contract Creation"}
                      </span>
                    </p>
                  </div>

                  {/* Flags */}
                  {threat.flags.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {threat.flags.map((flag, fi) => {
                        const isCritical =
                          flag.startsWith("CRITICAL") ||
                          flag.startsWith("MIXER");
                        return (
                          <span
                            key={fi}
                            className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[11px] font-medium ${
                              isCritical
                                ? "bg-red-500/20 text-red-300 border border-red-500/30"
                                : "bg-amber-500/15 text-amber-300 border border-amber-500/25"
                            }`}
                          >
                            <svg
                              className="h-2.5 w-2.5"
                              fill="none"
                              viewBox="0 0 24 24"
                              stroke="currentColor"
                              strokeWidth={2.5}
                            >
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                              />
                            </svg>
                            {flag.length > 80
                              ? flag.slice(0, 77) + "..."
                              : flag}
                          </span>
                        );
                      })}
                    </div>
                  )}

                  {/* Tx hash */}
                  <p className="mt-2 truncate text-[10px] font-mono text-zinc-600">
                    TX {threat.transaction_hash}
                  </p>
                </motion.div>
              );
            })}
          </AnimatePresence>
        </div>
      </div>
    </section>
  );
}
