import { useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { getDashboard, getFailures, exportCSV, uploadLog, getExplanation, getRuns, logout } from "../api/api";
import HealthScore from "./HealthScore";
import CategoryDistribution from "./CategoryDistribution";
import FailurePriorityTable from "./FailurePriorityTable";
import ModuleHotspot from "./ModuleHotspot";
import FailureTimeline from "./FailureTimeline";
import RootCauseSuggestion from "./RootCauseSuggestion";
import GraphView from "./GraphView";
import PriorityHeatmap from "./PriorityHeatmap";

const Dashboard = () => {
  const { runId } = useParams();
  const navigate = useNavigate();
  const [dashboard, setDashboard] = useState(null);
  const [failures, setFailures] = useState([]);
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [explain, setExplain] = useState(null);
  const [shapImportance, setShapImportance] = useState(null);
  const [explainLoading, setExplainLoading] = useState(false);
  const [graphMode, setGraphMode] = useState("cluster");

  const [runs, setRuns] = useState([]);
  const [runsLoading, setRunsLoading] = useState(false);
  const [runsOffset, setRunsOffset] = useState(0);
  const runsLimit = 8;

  useEffect(() => {
    if (!runId) {
      setDashboard({
        health_score: 0,
        total_failures: 0,
        unique_failures: 0,
        critical_count: 0,
        category_distribution: [],
        module_hotspots: [],
        priority_ranking: [],
        failure_clusters: [],
        failure_timeline: [],
        root_cause_suggestions: [],
        debug_recommendations: [],
      });
      setFailures([]);
      setSelected(null);
      setLoading(false);
      return;
    }

    const fetchAll = async () => {
      try {
        const [dashRes, failRes] = await Promise.all([
          getDashboard(runId),
          getFailures(runId),
        ]);
        setDashboard(dashRes.data);
        setFailures(failRes.data);
        setSelected(failRes.data[0] || null);
      } catch (err) {
          if (err?.response?.status === 401) {
            navigate("/login");
            return;
          }
          setError(err?.response?.data?.detail || "Failed to load dashboard");
      } finally {
        setLoading(false);
      }
    };
    fetchAll();
  }, [runId]);

  useEffect(() => {
    let cancelled = false;
    const loadRuns = async () => {
      setRunsLoading(true);
      try {
        const res = await getRuns({ limit: runsLimit, offset: runsOffset });
        if (!cancelled) setRuns(res.data || []);
      } catch (err) {
        if (err?.response?.status === 401) {
          localStorage.removeItem("debugiq_token");
          navigate("/login");
          return;
        }
        if (!cancelled) setRuns([]);
      } finally {
        if (!cancelled) setRunsLoading(false);
      }
    };
    loadRuns();
    return () => {
      cancelled = true;
    };
  }, [runsOffset]);

  useEffect(() => {
    if (!runId || !selected?.id) {
      setExplain(null);
      setShapImportance(null);
      return;
    }

    let cancelled = false;
    const loadExplanation = async () => {
      setExplainLoading(true);
      try {
        const res = await getExplanation(runId, selected.id);
        if (cancelled) return;
        setExplain(res.data.llm_explanation);
        setShapImportance(res.data.shap_importance);
      } catch (err) {
        if (err?.response?.status === 401) {
          navigate("/login");
          return;
        }
        if (!cancelled) {
          setExplain(null);
          setShapImportance(null);
        }
      } finally {
        if (!cancelled) setExplainLoading(false);
      }
    };

    loadExplanation();
    return () => {
      cancelled = true;
    };
  }, [runId, selected?.id]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="flex items-center gap-3 glass px-6 py-4 rounded-xl card-glow">
          <div className="h-5 w-5 border-2 border-emerald-400 border-t-transparent rounded-full animate-spin" />
          <span className="text-slate-200 text-sm">Loading dashboard...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="glass px-6 py-4 rounded-xl text-red-400">{error}</div>
      </div>
    );
  }

  const suggestion = dashboard.root_cause_suggestions.find((s) => s.failure_id === selected?.id)?.suggestion;
  const recommendation = dashboard.debug_recommendations.find((r) => r.failure_id === selected?.id)?.recommendation;

  const severities = ["INFO", "WARNING", "ERROR", "FATAL"];
  const modules = [...new Set(failures.map((f) => f.module))];
  const heatmapData = modules.map((mod) =>
    severities.map((sev) => failures.filter((f) => f.module === mod && f.severity === sev).length)
  );

  const graphNodes = failures.map((f) => ({
    id: f.id,
    group: f.cluster_id,
    name: f.module,
    category: f.category,
    severity: f.severity,
    unique_failure_id: f.unique_failure_id,
  }));
  const clusterEdges = [];
  for (let i = 1; i < failures.length; i++) {
    if (failures[i].module === failures[i - 1].module) {
      clusterEdges.push({ source: failures[i - 1].id, target: failures[i].id });
    }
  }
  const rootEdges = [];
  const ufMap = new Map();
  failures.forEach((f) => {
    const key = f.unique_failure_id;
    if (!ufMap.has(key)) {
      ufMap.set(key, f.id);
    } else {
      rootEdges.push({ source: ufMap.get(key), target: f.id });
    }
  });
  const graphEdges = graphMode === "root" ? rootEdges : clusterEdges;

  return (
    <div className="min-h-screen flex">
      <aside className="hidden lg:flex w-72 flex-col gap-6 px-6 py-6 bg-slate-950/70 border-r border-slate-800">
        <div>
          <div className="text-xs text-emerald-400 uppercase tracking-[0.2em] mono">DebugIQ</div>
          <div className="text-xl font-semibold mt-2">Log Intelligence</div>
        </div>

        <div className="glass rounded-xl p-4">
          <div className="text-xs text-slate-400 mb-2">Reports</div>
          <button
            onClick={() => runId && exportCSV(runId)}
            className="w-full bg-emerald-500 hover:bg-emerald-400 text-sm px-3 py-2 rounded mb-2 disabled:opacity-50"
            disabled={!runId}
          >
            Export CSV
          </button>
          <Link to="/upload" className="w-full block text-center bg-slate-800 hover:bg-slate-700 text-sm px-3 py-2 rounded">
            Upload New Log
          </Link>
          <button
            onClick={async () => {
              try {
                await logout();
              } catch {
                // Best-effort; still clear token locally.
              } finally {
                localStorage.removeItem("debugiq_token");
                navigate("/login");
              }
            }}
            className="w-full bg-slate-900 hover:bg-slate-800 text-sm px-3 py-2 rounded mt-2 border border-slate-700 text-slate-300"
          >
            Logout
          </button>
        </div>

        <div className="glass rounded-xl p-4 text-sm text-slate-300">
          <div className="text-xs text-slate-500 mb-2">Run ID</div>
          <div className="mono text-emerald-300">{runId ? `#${runId}` : "No run loaded"}</div>
        </div>

        <div className="glass rounded-xl p-4 text-sm text-slate-300">
          <div className="text-xs text-slate-400 mb-2">Recent Runs</div>
          {runsLoading && <div className="text-xs text-slate-500">Loading…</div>}
          {!runsLoading && runs.length === 0 && (
            <div className="text-xs text-slate-500">No runs yet.</div>
          )}
          {!runsLoading && runs.length > 0 && (
            <div className="space-y-2">
              {runs.map((r) => (
                <button
                  key={r.id}
                  onClick={() => navigate(`/dashboard/${r.id}`)}
                  className={`w-full text-left px-2 py-2 rounded border ${
                    String(runId) === String(r.id)
                      ? "bg-emerald-500/10 border-emerald-400/20 text-emerald-200"
                      : "bg-slate-900/30 border-slate-800 hover:bg-slate-900/50 text-slate-300"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="mono text-xs">#{r.id}</span>
                    <span className="text-[11px] text-slate-500">
                      {r.total_failures ?? 0} fails
                    </span>
                  </div>
                  <div className="text-[11px] text-slate-400 truncate">
                    {r.filename || "upload.log"}
                  </div>
                </button>
              ))}
            </div>
          )}
          <div className="flex items-center gap-2 mt-3">
            <button
              className="flex-1 bg-slate-900 hover:bg-slate-800 text-xs px-3 py-2 rounded border border-slate-800 disabled:opacity-50"
              disabled={runsOffset === 0 || runsLoading}
              onClick={() => setRunsOffset((o) => Math.max(0, o - runsLimit))}
            >
              Prev
            </button>
            <button
              className="flex-1 bg-slate-900 hover:bg-slate-800 text-xs px-3 py-2 rounded border border-slate-800 disabled:opacity-50"
              disabled={runs.length < runsLimit || runsLoading}
              onClick={() => setRunsOffset((o) => o + runsLimit)}
            >
              Next
            </button>
          </div>
        </div>

        <div className="mt-auto text-xs text-slate-500">v2.0 Prototype</div>
      </aside>

      <main className="flex-1 px-6 py-6 lg:px-10">
        <header className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 mb-6">
          <div>
            <div className="text-xs text-slate-400 uppercase tracking-[0.2em] mono">Prototype</div>
            <h1 className="text-3xl font-semibold">DebugIQ Priority Dashboard</h1>
            <p className="text-slate-400 text-sm mt-1">AI-ranked failures, clustered by root cause.</p>
          </div>
          <div className="flex items-center gap-3">
            <span className="px-3 py-1 rounded-full text-xs bg-emerald-400/10 text-emerald-300 border border-emerald-400/20">Live Analysis</span>
            <span className="px-3 py-1 rounded-full text-xs bg-slate-800 text-slate-300 border border-slate-700">
              {runId ? `Run #${runId}` : "Awaiting Upload"}
            </span>
          </div>
        </header>

        <section className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <HealthScore score={dashboard.health_score} />
          <div className="glass rounded-xl p-4 card-glow">
            <div className="text-xs text-slate-400">Total Failures</div>
            <div className="text-2xl font-semibold mt-2">{dashboard.total_failures}</div>
          </div>
          <div className="glass rounded-xl p-4 card-glow">
            <div className="text-xs text-slate-400">Unique Failures</div>
            <div className="text-2xl font-semibold mt-2">{dashboard.unique_failures}</div>
          </div>
          <div className="glass rounded-xl p-4 card-glow">
            <div className="text-xs text-slate-400">Critical Issues</div>
            <div className="text-2xl font-semibold mt-2 text-red-400">{dashboard.critical_count}</div>
          </div>
        </section>

        <section className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
          <CategoryDistribution data={dashboard.category_distribution} />
          <ModuleHotspot data={dashboard.module_hotspots} />
        </section>

        <section className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
          <div className="lg:col-span-2">
            <FailurePriorityTable data={dashboard.priority_ranking} onSelect={(row) => {
              const match = failures.find((f) => f.unique_failure_id === row.unique_failure_id) || failures[0];
              setSelected(match);
            }} />
          </div>
          <div className="glass rounded-xl p-4 card-glow">
            <div className="text-xs text-slate-400 mb-2">Selected Failure</div>
            <div className="text-lg font-semibold mb-2">{selected?.module || "-"}</div>
            <div className="text-sm text-slate-300 mb-1">{selected?.category || "-"}</div>
            <div className="text-xs text-slate-500">{selected?.message || "Select a failure to inspect."}</div>
            {selected?.context && (
              <div className="mt-3">
                <div className="text-xs text-slate-400 mb-2">Log Context</div>
                <pre className="text-[11px] text-slate-300 whitespace-pre-wrap max-h-40 overflow-auto bg-slate-900/60 p-2 rounded">
                  {selected.context}
                </pre>
              </div>
            )}

            <div className="mt-3">
              <div className="text-xs text-slate-400 mb-2">AI Explanation</div>
              {explainLoading && (
                <div className="text-xs text-slate-500">Generating explanation...</div>
              )}
              {!explainLoading && explain && (
                <>
                  <pre className="text-[11px] text-slate-300 whitespace-pre-wrap max-h-48 overflow-auto bg-slate-900/60 p-2 rounded">
                    {explain}
                  </pre>
                  {shapImportance && (
                    <div className="mt-3">
                      <div className="text-xs text-slate-500 mb-2">Feature Importance (SHAP)</div>
                      <div className="text-xs text-slate-300">
                        {Object.entries(shapImportance).map(([k, v]) => (
                          <div key={k}>
                            {k}: {v}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              )}
              {!explainLoading && !explain && (
                <div className="text-xs text-slate-500">Explanation will appear here.</div>
              )}
            </div>
          </div>
        </section>

        <section className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <button
                className={`text-xs px-3 py-1 rounded-full border ${
                  graphMode === "cluster"
                    ? "bg-emerald-500/20 text-emerald-300 border-emerald-400/30"
                    : "bg-slate-800 text-slate-300 border-slate-700"
                }`}
                onClick={() => setGraphMode("cluster")}
              >
                Cluster View
              </button>
              <button
                className={`text-xs px-3 py-1 rounded-full border ${
                  graphMode === "root"
                    ? "bg-emerald-500/20 text-emerald-300 border-emerald-400/30"
                    : "bg-slate-800 text-slate-300 border-slate-700"
                }`}
                onClick={() => setGraphMode("root")}
              >
                Root Cause View
              </button>
            </div>
            <GraphView nodes={graphNodes} edges={graphEdges} />
          </div>
          <FailureTimeline data={dashboard.failure_timeline} />
        </section>

        <PriorityHeatmap xLabels={severities} yLabels={modules} data={heatmapData} />

        <RootCauseSuggestion suggestion={suggestion} recommendation={recommendation} />

        {!runId && (
          <section className="glass rounded-2xl p-8 card-glow mt-6">
            <div className="text-xs text-emerald-400 uppercase tracking-[0.2em] mono">Upload</div>
            <h2 className="text-xl font-semibold mt-2">Add a regression log to populate the dashboard</h2>
            <p className="text-slate-400 text-sm mt-1">Drop .log, .txt, or .gz and the charts will update instantly.</p>
            <div className="mt-6">
              <label className="block text-sm text-slate-300 mb-2">Upload Log File</label>
              <input
                type="file"
                accept=".log,.txt,.gz"
                onChange={async (e) => {
                  const file = e.target.files?.[0];
                  if (!file) return;
                  try {
                    const res = await uploadLog(file);
                    navigate(`/dashboard/${res.data.run_id}`);
                  } catch (err) {
                    setError(err?.response?.data?.detail || "Upload failed");
                  }
                }}
                className="block w-full text-sm text-slate-300 file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:text-sm file:bg-emerald-500 file:text-white hover:file:bg-emerald-400"
              />
            </div>
          </section>
        )}
      </main>
    </div>
  );
};

export default Dashboard;
