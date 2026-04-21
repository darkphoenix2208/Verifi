import { useEffect, useState } from "react";
import { motion } from "framer-motion";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

interface FeatureImportance {
  name: string;
  importance: number;
}

interface MLModel {
  id: string;
  name: string;
  type: string;
  status: string;
  features: string[];
  feature_importances: FeatureImportance[];
  training_samples: number;
  technique: string;
  explainability: string;
  anomaly_threshold?: number;
}

interface ObservatoryData {
  total_models: number;
  models: MLModel[];
}

const STATUS_COLORS: Record<string, { dot: string; label: string }> = {
  active: { dot: "bg-emerald-400", label: "text-emerald-400" },
  fallback: { dot: "bg-amber-400", label: "text-amber-400" },
  inactive: { dot: "bg-zinc-500", label: "text-zinc-500" },
  unavailable: { dot: "bg-red-400", label: "text-red-400" },
};

const MODEL_ICONS: Record<string, string> = {
  "transaction-fraud": "M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z",
  "employee-risk": "M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z",
  "behavior-gmm": "M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z",
  "crypto-isolation": "M13 10V3L4 14h7v7l9-11h-7z",
};

const GRADIENT_COLORS: Record<string, string> = {
  "transaction-fraud": "from-blue-600 to-cyan-500",
  "employee-risk": "from-orange-500 to-amber-400",
  "behavior-gmm": "from-emerald-500 to-teal-400",
  "crypto-isolation": "from-violet-600 to-purple-500",
};

export function MLObservatoryDashboard() {
  const [data, setData] = useState<ObservatoryData | null>(null);
  const [loading, setLoading] = useState(true);
  const [expandedModel, setExpandedModel] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API_BASE_URL}/api/ml/observatory`)
      .then((r) => r.json())
      .then((d) => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-zinc-700 border-t-cyan-500" />
      </div>
    );
  }

  if (!data) {
    return <p className="text-center text-zinc-500">Failed to load observatory data.</p>;
  }

  return (
    <section className="mx-auto w-full max-w-6xl space-y-5">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-cyan-600 to-blue-500 shadow-lg shadow-cyan-500/20">
          <svg className="h-5 w-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0112 15a9.065 9.065 0 00-6.23.693L5 14.5m14.8.8l1.402 1.402c1.232 1.232.65 3.318-1.067 3.611A48.309 48.309 0 0112 21c-2.773 0-5.491-.235-8.135-.687-1.718-.293-2.3-2.379-1.067-3.61L5 14.5" />
          </svg>
        </div>
        <div>
          <h2 className="text-lg font-bold text-zinc-100">ML Model Observatory</h2>
          <p className="text-xs font-mono tracking-wider text-zinc-500 uppercase">{data.total_models} Active Models</p>
        </div>
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[
          { label: "Models", value: data.total_models, color: "text-cyan-400" },
          { label: "Active", value: data.models.filter(m => m.status === "active").length, color: "text-emerald-400" },
          { label: "Total Features", value: data.models.reduce((sum, m) => sum + m.features.length, 0), color: "text-blue-400" },
          { label: "Training Samples", value: data.models.reduce((sum, m) => sum + m.training_samples, 0).toLocaleString(), color: "text-violet-400" },
        ].map((stat, i) => (
          <div key={i} className="rounded-xl border border-zinc-800 bg-zinc-900/80 p-4 text-center">
            <p className={`text-2xl font-black ${stat.color}`}>{stat.value}</p>
            <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">{stat.label}</p>
          </div>
        ))}
      </div>

      {/* Model cards */}
      <div className="grid gap-4 md:grid-cols-2">
        {data.models.map((model, idx) => {
          const sc = STATUS_COLORS[model.status] || STATUS_COLORS.inactive;
          const grad = GRADIENT_COLORS[model.id] || "from-zinc-600 to-zinc-500";
          const icon = MODEL_ICONS[model.id] || "M13 10V3L4 14h7v7l9-11h-7z";
          const isExpanded = expandedModel === model.id;
          const maxImportance = Math.max(...model.feature_importances.map((f) => f.importance));

          return (
            <motion.div
              key={model.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: idx * 0.08 }}
              className="rounded-2xl border border-zinc-800 bg-zinc-900/80 overflow-hidden"
            >
              {/* Accent bar */}
              <div className={`h-1 w-full bg-gradient-to-r ${grad}`} />

              <div className="p-5">
                {/* Header */}
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className={`flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br ${grad} shadow-lg`}>
                      <svg className="h-5 w-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
                        <path strokeLinecap="round" strokeLinejoin="round" d={icon} />
                      </svg>
                    </div>
                    <div>
                      <p className="text-sm font-bold text-zinc-100">{model.name}</p>
                      <p className="text-[11px] font-mono text-zinc-500">{model.type}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className={`h-2 w-2 rounded-full ${sc.dot} animate-pulse`} />
                    <span className={`text-[10px] font-semibold uppercase ${sc.label}`}>{model.status}</span>
                  </div>
                </div>

                {/* Quick stats */}
                <div className="mt-4 grid grid-cols-3 gap-2">
                  <div className="rounded-lg bg-zinc-950/50 px-2 py-1.5 text-center">
                    <p className="text-lg font-bold text-zinc-200">{model.features.length}</p>
                    <p className="text-[9px] font-semibold uppercase tracking-wider text-zinc-600">Features</p>
                  </div>
                  <div className="rounded-lg bg-zinc-950/50 px-2 py-1.5 text-center">
                    <p className="text-lg font-bold text-zinc-200">{model.training_samples >= 1000 ? `${(model.training_samples / 1000).toFixed(0)}K` : model.training_samples}</p>
                    <p className="text-[9px] font-semibold uppercase tracking-wider text-zinc-600">Samples</p>
                  </div>
                  <div className="rounded-lg bg-zinc-950/50 px-2 py-1.5 text-center">
                    <p className="text-[10px] font-bold text-zinc-200 leading-tight mt-1">{model.explainability.split(" ")[0]}</p>
                    <p className="text-[9px] font-semibold uppercase tracking-wider text-zinc-600">XAI</p>
                  </div>
                </div>

                {/* Feature importance bars */}
                <button
                  type="button"
                  onClick={() => setExpandedModel(isExpanded ? null : model.id)}
                  className="mt-3 w-full text-left text-[11px] font-semibold uppercase tracking-wider text-zinc-500 transition hover:text-zinc-300"
                >
                  {isExpanded ? "▾ Hide" : "▸ Show"} Feature Importance
                </button>

                {isExpanded && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                    className="mt-3 space-y-1.5"
                  >
                    {model.feature_importances.map((fi, i) => (
                      <div key={i} className="flex items-center gap-2">
                        <span className="w-32 truncate text-[11px] font-mono text-zinc-400">{fi.name}</span>
                        <div className="flex-1 h-3 rounded-full bg-zinc-800 overflow-hidden">
                          <motion.div
                            initial={{ width: 0 }}
                            animate={{ width: `${(fi.importance / maxImportance) * 100}%` }}
                            transition={{ delay: i * 0.05, duration: 0.4 }}
                            className={`h-full rounded-full bg-gradient-to-r ${grad}`}
                          />
                        </div>
                        <span className="w-10 text-right text-[11px] font-mono text-zinc-500">{(fi.importance * 100).toFixed(0)}%</span>
                      </div>
                    ))}
                    <p className="mt-2 text-[10px] text-zinc-600">
                      <span className="font-semibold text-zinc-500">Technique:</span> {model.technique}
                    </p>
                  </motion.div>
                )}
              </div>
            </motion.div>
          );
        })}
      </div>
    </section>
  );
}
