import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";

interface EmployeeRiskItem {
  employeeId: string;
  name: string;
  team: string;
  riskScore: number;
  riskLevel: "LOW" | "MEDIUM" | "HIGH";
  topFactors: string[];
}

interface FactorDatum {
  factor: string;
  impact: number;
}

// API response shape from GET /api/employee/risk
interface ApiEmployeeRiskItem {
  employee_id: string;
  risk_score: number;
  risk_level: string;
  top_factors: string[];
}

interface ApiEmployeeRiskResponse {
  generated_at: number;
  model_name: string;
  items: ApiEmployeeRiskItem[];
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

function mapApiToLocal(item: ApiEmployeeRiskItem): EmployeeRiskItem {
  const level = item.risk_level.toUpperCase();
  return {
    employeeId: item.employee_id,
    name: item.employee_id,       // Use ID as display name; API doesn't return names
    team: level === "HIGH" ? "Flagged" : level === "MEDIUM" ? "Under Review" : "Normal",
    riskScore: item.risk_score,
    riskLevel: (level === "HIGH" || level === "MEDIUM" || level === "LOW" ? level : "LOW") as EmployeeRiskItem["riskLevel"],
    topFactors: item.top_factors,
  };
}

function riskLevelClasses(level: EmployeeRiskItem["riskLevel"]): string {
  if (level === "HIGH") {
    return "bg-red-500/20 text-red-300";
  }
  if (level === "MEDIUM") {
    return "bg-amber-500/20 text-amber-300";
  }
  return "bg-emerald-500/20 text-emerald-300";
}

function factorImpact(score: number, index: number): number {
  const weights = [0.44, 0.33, 0.23];
  return Number((score * (weights[index] ?? 0.1)).toFixed(3));
}

export function EmployeeRiskDashboard() {
  const [employeeData, setEmployeeData] = useState<EmployeeRiskItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string>("");
  const [modelName, setModelName] = useState<string>("");
  const [generatedAt, setGeneratedAt] = useState<number>(0);

  // Fetch live data from GET /api/employee/risk
  useEffect(() => {
    let cancelled = false;

    const fetchEmployeeRisk = async () => {
      setLoading(true);
      setFetchError("");
      try {
        const response = await fetch(`${API_BASE_URL}/api/employee/risk`);
        if (!response.ok) {
          const body = await response.json().catch(() => ({}));
          throw new Error((body as { detail?: string }).detail ?? `API returned ${response.status}`);
        }
        const data = (await response.json()) as ApiEmployeeRiskResponse;
        if (!cancelled) {
          setEmployeeData(data.items.map(mapApiToLocal));
          setModelName(data.model_name);
          setGeneratedAt(data.generated_at);
        }
      } catch (err) {
        if (!cancelled) {
          setFetchError(err instanceof Error ? err.message : "Failed to fetch employee risk data.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    fetchEmployeeRisk();

    return () => {
      cancelled = true;
    };
  }, []);

  const [selectedEmployeeId, setSelectedEmployeeId] = useState<string>("");

  // Auto-select first employee when data arrives
  useEffect(() => {
    if (employeeData.length > 0 && !selectedEmployeeId) {
      setSelectedEmployeeId(employeeData[0].employeeId);
    }
  }, [employeeData, selectedEmployeeId]);

  const selectedEmployee =
    employeeData.find((employee) => employee.employeeId === selectedEmployeeId) ?? employeeData[0] ?? null;

  const factorData = useMemo<FactorDatum[]>(() => {
    if (!selectedEmployee) return [];
    return selectedEmployee.topFactors.map((factor, index) => ({
      factor,
      impact: factorImpact(selectedEmployee.riskScore, index)
    }));
  }, [selectedEmployee]);

  return (
    <section className="mx-auto w-full max-w-7xl space-y-6">
      <header className="rounded-2xl border border-zinc-800 bg-zinc-900 p-5">
        <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
          <div>
            <h2 className="text-2xl font-semibold text-zinc-100">Employee Risk Dashboard</h2>
            <p className="mt-1 text-sm text-zinc-400">
              Explainable AI view of employee fraud risk from your Random Forest model outputs.
            </p>
          </div>
          {modelName && (
            <div className="text-right">
              <span className="inline-flex items-center rounded-full border border-zinc-700 bg-zinc-950 px-3 py-1 text-xs font-semibold text-zinc-300">
                Model: {modelName}
              </span>
              {generatedAt > 0 && (
                <p className="mt-1 text-xs text-zinc-500">
                  Scored at {new Date(generatedAt * 1000).toLocaleString()}
                </p>
              )}
            </div>
          )}
        </div>
      </header>

      {fetchError && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {fetchError}
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center rounded-2xl border border-zinc-800 bg-zinc-900 px-4 py-16">
          <div className="flex items-center gap-3 text-sm text-zinc-400">
            <svg className="h-5 w-5 animate-spin" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
            </svg>
            Fetching employee risk scores from API...
          </div>
        </div>
      ) : employeeData.length === 0 && !fetchError ? (
        <div className="rounded-2xl border border-zinc-800 bg-zinc-900 px-4 py-16 text-center text-sm text-zinc-400">
          No employee risk data available.
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[360px,1fr]">
          <div className="rounded-2xl border border-zinc-800 bg-zinc-900 p-4">
            <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-400">Employees</h3>
            <div className="space-y-2">
              {employeeData.map((employee) => (
                <button
                  key={employee.employeeId}
                  type="button"
                  onClick={() => setSelectedEmployeeId(employee.employeeId)}
                  className={`w-full rounded-xl border p-3 text-left transition ${
                    selectedEmployeeId === employee.employeeId
                      ? "border-blue-500/60 bg-blue-500/10"
                      : "border-zinc-800 bg-zinc-950 hover:border-zinc-700"
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="text-sm font-semibold text-zinc-100">{employee.name}</p>
                      <p className="text-xs text-zinc-400">
                        {employee.employeeId} • {employee.team}
                      </p>
                    </div>
                    <span className={`rounded-full px-2 py-1 text-xs font-semibold ${riskLevelClasses(employee.riskLevel)}`}>
                      {employee.riskLevel}
                    </span>
                  </div>
                  <p className="mt-2 text-xs text-zinc-400">Risk Score</p>
                  <p className="text-lg font-bold text-zinc-100">{(employee.riskScore * 100).toFixed(1)}%</p>
                </button>
              ))}
            </div>
          </div>

          {selectedEmployee && (
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900 p-5">
              <div className="mb-4">
                <h3 className="text-lg font-semibold text-zinc-100">
                  XAI Factors for {selectedEmployee.name}
                </h3>
                <p className="text-sm text-zinc-400">
                  Factor contribution values aligned to current employee risk score.
                </p>
              </div>

              <div className="h-[320px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={factorData} margin={{ top: 10, right: 10, left: 0, bottom: 28 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#3f3f46" />
                    <XAxis
                      dataKey="factor"
                      stroke="#a1a1aa"
                      angle={-12}
                      textAnchor="end"
                      interval={0}
                      height={60}
                    />
                    <YAxis stroke="#a1a1aa" />
                    <Tooltip
                      cursor={{ fill: "rgba(63,63,70,0.2)" }}
                      contentStyle={{
                        backgroundColor: "#111827",
                        border: "1px solid #3f3f46",
                        borderRadius: "0.75rem",
                        color: "#f4f4f5"
                      }}
                    />
                    <Bar dataKey="impact" radius={[8, 8, 0, 0]}>
                      {factorData.map((entry) => (
                        <Cell
                          key={entry.factor}
                          fill={
                            selectedEmployee.riskLevel === "HIGH"
                              ? "#ef4444"
                              : selectedEmployee.riskLevel === "MEDIUM"
                                ? "#f59e0b"
                                : "#22c55e"
                          }
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>

              <div className="mt-5 rounded-xl border border-zinc-800 bg-zinc-950 p-4">
                <p className="text-xs uppercase tracking-wide text-zinc-400">Top Factors</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {selectedEmployee.topFactors.map((factor) => (
                    <span key={factor} className="rounded-full border border-zinc-700 px-3 py-1 text-xs text-zinc-300">
                      {factor}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
