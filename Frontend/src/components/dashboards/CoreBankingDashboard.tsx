import { useEffect, useMemo, useRef, useState } from "react";
import { connectTransactionsSocket, getTransactionsWsUrl } from "../../services/wsService";

interface TransactionEvent {
  transaction_id: string;
  account_id: string;
  amount: number;
  currency: string;
  risk_score: number;
  decision: "ALLOW" | "FLAG" | string;
  reason: string;
  ts: number;
}

interface InvestigateResponse {
  customer_id: string;
  report: string;
  recommended_actions: string[];
  generated_at: number;
}

type ConnectionStatus = "connecting" | "connected" | "disconnected" | "error";

const MAX_ROWS = 30;
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

function currencyFormat(currency: string, value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    maximumFractionDigits: 2
  }).format(value);
}

function timeFormat(ts: number): string {
  return new Date(ts * 1000).toLocaleTimeString();
}

export function CoreBankingDashboard() {
  const [transactions, setTransactions] = useState<TransactionEvent[]>([]);
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>("connecting");
  const [errorMessage, setErrorMessage] = useState<string>("");
  const socketRef = useRef<WebSocket | null>(null);
  const retryRef = useRef<number | null>(null);

  // Investigation modal state
  const [modalOpen, setModalOpen] = useState(false);
  const [investigatingTx, setInvestigatingTx] = useState<TransactionEvent | null>(null);
  const [investigateLoading, setInvestigateLoading] = useState(false);
  const [investigateResult, setInvestigateResult] = useState<InvestigateResponse | null>(null);
  const [investigateError, setInvestigateError] = useState<string>("");

  useEffect(() => {
    let isUnmounted = false;

    const connect = () => {
      if (isUnmounted) {
        return;
      }
      setConnectionStatus("connecting");
      const wsUrl = getTransactionsWsUrl();
      console.info("[FraudGuardian][WS] Connecting to:", wsUrl);
      const socket = connectTransactionsSocket();
      socketRef.current = socket;

      socket.onopen = () => {
        if (isUnmounted) {
          return;
        }
        console.info("[FraudGuardian][WS] Connected");
        setConnectionStatus("connected");
        setErrorMessage("");
      };

      socket.onerror = (event) => {
        if (isUnmounted) {
          return;
        }
        console.error("[FraudGuardian][WS] Error event:", event);
        setConnectionStatus("error");
        setErrorMessage("Live transaction stream encountered an error. Check browser console for details.");
      };

      socket.onmessage = (event) => {
        if (isUnmounted) {
          return;
        }
        try {
          const payload = JSON.parse(event.data) as TransactionEvent;
          setTransactions((prev) => [payload, ...prev].slice(0, MAX_ROWS));
        } catch {
          setErrorMessage("Received malformed transaction payload.");
        }
      };

      socket.onclose = (event) => {
        if (isUnmounted) {
          return;
        }
        console.warn(
          `[FraudGuardian][WS] Closed code=${event.code} reason=${event.reason || "no-reason"} clean=${event.wasClean}`
        );
        setConnectionStatus("disconnected");
        retryRef.current = window.setTimeout(connect, 2000);
      };
    };

    connect();

    return () => {
      isUnmounted = true;
      if (retryRef.current) {
        window.clearTimeout(retryRef.current);
      }
      if (socketRef.current) {
        socketRef.current.close();
      }
    };
  }, []);

  const flaggedTransactions = useMemo(
    () => transactions.filter((tx) => tx.decision === "FLAG").length,
    [transactions]
  );

  const totalVolume = useMemo(
    () => transactions.reduce((sum, tx) => sum + tx.amount, 0),
    [transactions]
  );

  const avgRiskScore = useMemo(() => {
    if (transactions.length === 0) {
      return 0;
    }
    const total = transactions.reduce((sum, tx) => sum + tx.risk_score, 0);
    return total / transactions.length;
  }, [transactions]);

  const statusPillClasses =
    connectionStatus === "connected"
      ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/30"
      : connectionStatus === "connecting"
        ? "bg-blue-500/20 text-blue-300 border-blue-500/30"
        : connectionStatus === "error"
          ? "bg-red-500/20 text-red-300 border-red-500/30"
          : "bg-zinc-500/20 text-zinc-300 border-zinc-500/30";

  // --- Investigate handler ---
  const handleInvestigate = async (tx: TransactionEvent) => {
    setInvestigatingTx(tx);
    setModalOpen(true);
    setInvestigateLoading(true);
    setInvestigateResult(null);
    setInvestigateError("");

    try {
      const response = await fetch(`${API_BASE_URL}/api/agent/investigate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          customer_id: tx.account_id,
          transaction_id: tx.transaction_id,
          incident_summary: `Transaction ${tx.transaction_id} flagged with risk score ${tx.risk_score.toFixed(3)}. Reason: ${tx.reason}. Amount: ${currencyFormat(tx.currency, tx.amount)}.`,
          evidence: {
            amount: tx.amount,
            currency: tx.currency,
            risk_score: tx.risk_score,
            decision: tx.decision,
            reason: tx.reason,
            timestamp: tx.ts,
          },
        }),
      });

      const body = await response.json();
      if (!response.ok) {
        throw new Error(body.detail ?? `Investigation failed (${response.status})`);
      }
      setInvestigateResult(body as InvestigateResponse);
    } catch (err) {
      setInvestigateError(err instanceof Error ? err.message : "Investigation request failed.");
    } finally {
      setInvestigateLoading(false);
    }
  };

  const closeModal = () => {
    setModalOpen(false);
    setInvestigatingTx(null);
    setInvestigateResult(null);
    setInvestigateError("");
  };

  return (
    <section className="mx-auto w-full max-w-7xl space-y-6">
      <header className="rounded-2xl border border-zinc-800 bg-zinc-900 p-5">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <h2 className="text-2xl font-semibold text-zinc-100">Core Banking Dashboard</h2>
            <p className="mt-1 text-sm text-zinc-400">
              Real-time fraud monitoring for transaction scoring and analyst response.
            </p>
          </div>
          <span className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold ${statusPillClasses}`}>
            Stream: {connectionStatus.toUpperCase()}
          </span>
        </div>
      </header>

      {errorMessage ? (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {errorMessage}
        </div>
      ) : null}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <div className="rounded-2xl border border-zinc-800 bg-zinc-900 p-5">
          <p className="text-xs uppercase tracking-wide text-zinc-400">Buffered Events</p>
          <p className="mt-2 text-3xl font-bold text-zinc-100">{transactions.length}</p>
        </div>
        <div className="rounded-2xl border border-zinc-800 bg-zinc-900 p-5">
          <p className="text-xs uppercase tracking-wide text-zinc-400">Flagged Transactions</p>
          <p className="mt-2 text-3xl font-bold text-red-300">{flaggedTransactions}</p>
        </div>
        <div className="rounded-2xl border border-zinc-800 bg-zinc-900 p-5">
          <p className="text-xs uppercase tracking-wide text-zinc-400">Observed Volume</p>
          <p className="mt-2 text-3xl font-bold text-zinc-100">{currencyFormat("USD", totalVolume)}</p>
          <p className="mt-1 text-xs text-zinc-400">Avg risk: {avgRiskScore.toFixed(2)}</p>
        </div>
      </div>

      <div className="overflow-hidden rounded-2xl border border-zinc-800 bg-zinc-900">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[1060px] text-left text-sm text-zinc-200">
            <thead className="bg-zinc-800/70 text-zinc-300">
              <tr>
                <th className="px-4 py-3 font-medium">Time</th>
                <th className="px-4 py-3 font-medium">Transaction ID</th>
                <th className="px-4 py-3 font-medium">Account ID</th>
                <th className="px-4 py-3 font-medium">Amount</th>
                <th className="px-4 py-3 font-medium">Risk Score</th>
                <th className="px-4 py-3 font-medium">Decision</th>
                <th className="px-4 py-3 font-medium">Reason</th>
                <th className="px-4 py-3 font-medium text-center">Action</th>
              </tr>
            </thead>
            <tbody>
              {transactions.length === 0 ? (
                <tr className="border-t border-zinc-800">
                  <td colSpan={8} className="px-4 py-10 text-center text-zinc-400">
                    Waiting for live transactions from WebSocket stream...
                  </td>
                </tr>
              ) : (
                transactions.map((tx) => (
                  <tr key={tx.transaction_id} className="border-t border-zinc-800 hover:bg-zinc-800/30">
                    <td className="px-4 py-3">{timeFormat(tx.ts)}</td>
                    <td className="px-4 py-3 font-medium text-zinc-100">{tx.transaction_id}</td>
                    <td className="px-4 py-3">{tx.account_id}</td>
                    <td className="px-4 py-3">{currencyFormat(tx.currency, tx.amount)}</td>
                    <td className="px-4 py-3">{tx.risk_score.toFixed(2)}</td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${
                          tx.decision === "FLAG"
                            ? "bg-red-500/20 text-red-300"
                            : "bg-emerald-500/20 text-emerald-300"
                        }`}
                      >
                        {tx.decision}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-zinc-300">{tx.reason}</td>
                    <td className="px-4 py-3 text-center">
                      <button
                        type="button"
                        onClick={() => handleInvestigate(tx)}
                        className="rounded-lg bg-amber-600/80 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-amber-500 disabled:opacity-40"
                      >
                        🔍 Investigate
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* ───────── Investigation Modal ───────── */}
      {modalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
          onClick={closeModal}
        >
          <div
            className="relative mx-4 max-h-[85vh] w-full max-w-2xl overflow-y-auto rounded-2xl border border-zinc-700 bg-zinc-900/95 p-6 shadow-2xl backdrop-blur-md"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Close button */}
            <button
              type="button"
              onClick={closeModal}
              className="absolute right-4 top-4 rounded-lg p-1 text-zinc-400 transition hover:bg-zinc-800 hover:text-zinc-100"
            >
              ✕
            </button>

            <h3 className="text-lg font-bold text-zinc-100">
              🤖 AI Investigation Report
            </h3>
            {investigatingTx && (
              <p className="mt-1 text-sm text-zinc-400">
                Transaction <span className="font-semibold text-zinc-200">{investigatingTx.transaction_id}</span>{" "}
                • Account <span className="font-semibold text-zinc-200">{investigatingTx.account_id}</span>{" "}
                • {currencyFormat(investigatingTx.currency, investigatingTx.amount)}
              </p>
            )}

            <div className="mt-5">
              {investigateLoading && (
                <div className="flex items-center gap-3 rounded-xl border border-blue-500/30 bg-blue-500/10 px-4 py-6 text-sm text-blue-300">
                  <svg className="h-5 w-5 animate-spin" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
                  </svg>
                  Agent is analyzing customer records and generating report...
                </div>
              )}

              {investigateError && (
                <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
                  {investigateError}
                </div>
              )}

              {investigateResult && (
                <div className="space-y-4">
                  <div className="rounded-xl border border-zinc-700 bg-zinc-950 p-4">
                    <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-zinc-400">Report</p>
                    <div className="whitespace-pre-wrap text-sm leading-relaxed text-zinc-200">
                      {investigateResult.report}
                    </div>
                  </div>

                  <div className="rounded-xl border border-zinc-700 bg-zinc-950 p-4">
                    <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-zinc-400">
                      Recommended Actions
                    </p>
                    <ul className="space-y-1.5">
                      {investigateResult.recommended_actions.map((action, idx) => (
                        <li key={idx} className="flex items-start gap-2 text-sm text-zinc-200">
                          <span className="mt-0.5 inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-amber-400" />
                          {action}
                        </li>
                      ))}
                    </ul>
                  </div>

                  <p className="text-xs text-zinc-500">
                    Generated at {new Date(investigateResult.generated_at * 1000).toLocaleString()}
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
