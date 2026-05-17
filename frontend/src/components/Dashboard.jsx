import { useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { getDashboard, getFailures, exportCSV, uploadLog, getExplanation, getRuns, logout, updateFailureStatus, deleteAllRuns } from "../api/api";
import HealthScore from "./HealthScore";
import CategoryDistribution from "./CategoryDistribution";
import FailurePriorityTable from "./FailurePriorityTable";
import ModuleHotspot from "./ModuleHotspot";
import ModuleEfficiency from "./ModuleEfficiency";
import FailureTimeline from "./FailureTimeline";
import RootCauseSuggestion from "./RootCauseSuggestion";
import GraphView from "./GraphView";
import PriorityHeatmap from "./PriorityHeatmap";
import RunChatPanel from "./RunChatPanel";

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
  const [explainError, setExplainError] = useState(null);
  const [graphMode, setGraphMode] = useState("cluster");
  const [statusUpdating, setStatusUpdating] = useState(false);
  const [statusError, setStatusError] = useState(null);

  const [runs, setRuns] = useState([]);
  const [runsLoading, setRunsLoading] = useState(false);
  const [runsOffset, setRunsOffset] = useState(0);
  const runsLimit = 8;
  const [chatOpen, setChatOpen] = useState(false);
  const activeRun = runs.find((r) => String(r.id) === String(runId));
  const activeRunName = runId ? activeRun?.filename || "Selected upload" : "No upload selected";

  useEffect(() => {
    if (!runId) {
      setDashboard({
        health_score: 0,
        total_failures: 0,
        unique_failures: 0,
        critical_count: 0,
        category_distribution: [],
        module_hotspots: [],
        module_efficiency: [],
        priority_ranking: [],
        failure_clusters: [],
        failure_timeline: [],
        root_cause_suggestions: [],
        debug_recommendations: [],
        new_failure_count: 0,
        known_failure_count: 0,
        recurrence_rate: 0,
        mttr_hours: null,
        status_breakdown: [],
        trend_vs_prev_run: null,
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
      setExplainError(null);
      return;
    }

    let cancelled = false;
    const loadExplanation = async () => {
      setExplainLoading(true);
      setExplainError(null);
      try {
        const res = await getExplanation(runId, selected.id);
        if (cancelled) return;
        let text = res.data.llm_explanation || "";
        if (/^\[MOCK LLM\]/i.test(text)) {
          setExplainError(
            "This response came from an old build. Restart the backend with valid GROQ_KEY / OPENAI_API_KEY / GEMINI_API_KEY."
          );
          text = text.replace(/^\[MOCK LLM\]\s*/i, "").trim();
        }
        setExplain(text || null);
        setShapImportance(res.data.shap_importance);
      } catch (err) {
        if (err?.response?.status === 401) {
          navigate("/login");
          return;
        }
        if (!cancelled) {
          setExplain(null);
          setShapImportance(null);
          const detail = err?.response?.data?.detail;
          setExplainError(
            typeof detail === "string" ? detail : err?.message || "Explanation request failed"
          );
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
  const statusOptions = ["open", "investigating", "closed", "wontfix"];

  const severities = ["INFO", "WARNING", "ERROR", "FATAL"];
  const modules = [...new Set(failures.map((f) => f.module))];
  const heatmapData = modules.map((mod) =>
    severities.map((sev) => failures.filter((f) => f.module === mod && f.severity === sev).length)
  );

  const graphNodes = failures.map((f) => ({
    id: f.id,
    group: f.cluster_id ?? 0,
    name: f.module,
    category: f.category,
    severity: f.severity,
    unique_failure_id: f.unique_failure_id,
    timestamp: f.timestamp,
  }));

  // Cluster view: connect each node to a cluster "hub" for readability.
  const clusterEdges = [];
  const clusterHub = new Map();
  for (const n of graphNodes) {
    const c = n.group ?? 0;
    if (!clusterHub.has(c)) {
      clusterHub.set(c, n.id);
    } else {
      clusterEdges.push({ source: clusterHub.get(c), target: n.id });
    }
  }
  // Fallback: if every node is isolated in its own cluster, render a light chain
  // so the cluster view is still visually interpretable.
  if (clusterEdges.length === 0 && graphNodes.length > 1) {
    const byCluster = [...graphNodes].sort((a, b) => (a.group ?? 0) - (b.group ?? 0));
    for (let i = 1; i < byCluster.length; i++) {
      clusterEdges.push({ source: byCluster[i - 1].id, target: byCluster[i].id });
    }
  }

  // Root cause view: temporal topology (connect each failure to up to 3 prior failures).
  const rootEdges = [];
  const sortedByTime = [...graphNodes].sort((a, b) => String(a.timestamp || "").localeCompare(String(b.timestamp || "")));
  for (let i = 0; i < sortedByTime.length; i++) {
    for (let j = Math.max(0, i - 3); j < i; j++) {
      rootEdges.push({ source: sortedByTime[j].id, target: sortedByTime[i].id });
    }
  }

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
          <div className="text-xs text-slate-500 mb-2">Selected Upload</div>
          <div className="text-emerald-300 font-medium truncate" title={activeRunName}>
            {activeRunName}
          </div>
          {runId && (
            <div className="mono text-[10px] text-slate-500 mt-1">Database ID {runId}</div>
          )}
        </div>

        <div className="glass rounded-xl p-4 text-sm text-slate-300">
          <div className="flex items-center justify-between gap-2 mb-2">
            <div className="text-xs text-slate-400">Recent Runs</div>
            <button
              type="button"
              title="Delete every run and failure for your account (upload history cleared)"
              className="text-[10px] uppercase tracking-wide text-red-400/90 hover:text-red-300 px-2 py-1 rounded border border-red-500/30 hover:border-red-400/50 disabled:opacity-40"
              disabled={runsLoading || runs.length === 0}
              onClick={async () => {
                if (
                  !window.confirm(
                    "Remove ALL your runs and failure records from DebugIQ? This cannot be undone."
                  )
                ) {
                  return;
                }
                try {
                  await deleteAllRuns();
                  setRunsOffset(0);
                  const res = await getRuns({ limit: runsLimit, offset: 0 });
                  setRuns(res.data || []);
                  navigate("/dashboard");
                } catch (err) {
                  setError(err?.response?.data?.detail || "Could not clear runs");
                }
              }}
            >
              Clear all
            </button>
          </div>
          <p className="text-[10px] text-slate-500 mb-2 leading-snug">
            These are saved uploads. The small database ID is only for deep links.
          </p>
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
                  <div className="text-[11px] text-slate-200 font-medium truncate" title={r.filename || ""}>
                    {r.filename || "upload.log"}
                  </div>
                  <div className="flex items-center justify-between mt-1">
                    <span className="mono text-[10px] text-slate-500">
                      ID {r.id}
                    </span>
                    <span className="text-[11px] text-slate-500">
                      {r.total_failures ?? 0} fails
                    </span>
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
          <div className="flex flex-wrap items-center gap-3">
            <span className="px-3 py-1 rounded-full text-xs bg-emerald-400/10 text-emerald-300 border border-emerald-400/20">Live Analysis</span>
            <span className="px-3 py-1 rounded-full text-xs bg-slate-800 text-slate-300 border border-slate-700">
              {runId ? activeRunName : "Awaiting upload"}
            </span>
            {!chatOpen && (
              <button
                type="button"
                onClick={() => setChatOpen(true)}
                title={runId ? "Open run assistant" : "Open assistant (pick a run to ask about failures)"}
                className="px-3 py-1.5 rounded-lg text-xs font-medium bg-emerald-600/90 hover:bg-emerald-500 text-white border border-emerald-400/30 shadow-lg shadow-emerald-900/20"
              >
                AI assistant
              </button>
            )}
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

        <section className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <div className="glass rounded-xl p-4 card-glow">
            <div className="text-xs text-slate-400">New vs Known</div>
            <div className="text-xl font-semibold mt-2">
              {dashboard.new_failure_count} new / {dashboard.known_failure_count} known
            </div>
          </div>
          <div className="glass rounded-xl p-4 card-glow">
            <div className="text-xs text-slate-400">Recurrence Rate</div>
            <div className="text-2xl font-semibold mt-2">{dashboard.recurrence_rate}%</div>
          </div>
          <div className="glass rounded-xl p-4 card-glow">
            <div className="text-xs text-slate-400">MTTR Estimate</div>
            <div className="text-2xl font-semibold mt-2">
              {dashboard.mttr_hours == null ? "—" : `${dashboard.mttr_hours}h`}
            </div>
          </div>
          <div className="glass rounded-xl p-4 card-glow">
            <div className="text-xs text-slate-400">Trend vs Prev Run</div>
            <div className="text-2xl font-semibold mt-2 capitalize">
              {dashboard.trend_vs_prev_run || "—"}
            </div>
          </div>
        </section>

        <section className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
          <CategoryDistribution data={dashboard.category_distribution} />
          <ModuleHotspot data={dashboard.module_hotspots} />
          <ModuleEfficiency data={dashboard.module_efficiency} />
        </section>

        <section className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
          <div className="lg:col-span-2">
            <FailurePriorityTable data={dashboard.priority_ranking} failures={failures} onSelect={(row) => {
              const match = failures.find((f) => f.unique_failure_id === row.unique_failure_id) || failures[0];
              setSelected(match);
            }} />
          </div>
          <div className="glass rounded-xl p-4 card-glow">
            <div className="text-xs text-slate-400 mb-2">Selected Failure</div>
            <div className="text-lg font-semibold mb-2">{selected?.module || "-"}</div>
            <div className="text-sm text-slate-300 mb-1">{selected?.category || "-"}</div>
            <div className="text-xs text-slate-500">
              {selected?.failure_type || "LOG"} · {selected?.severity_raw || selected?.severity || "-"}
            </div>
            {selected?.uvm_phase && (
              <div className="text-xs text-slate-500 mt-1">Phase: {selected.uvm_phase}</div>
            )}
            <div className="text-xs text-slate-500">{selected?.message || "Select a failure to inspect."}</div>
            {selected?.test_name && (
              <div className="text-xs text-slate-500 mt-2">Test: {selected.test_name}</div>
            )}
            {selected?.seed && (
              <div className="text-xs text-slate-500">Seed: {selected.seed}</div>
            )}
            {selected?.dut_path && (
              <div className="text-xs text-slate-500">DUT: {selected.dut_path}</div>
            )}
            {selected?.sim_time && (
              <div className="text-xs text-slate-500">Sim Time: {selected.sim_time}</div>
            )}
            <div className="mt-3">
              <div className="text-xs text-slate-400 mb-2">Debug Status</div>
              <div className="flex items-center gap-2">
                <select
                  className="bg-slate-900/60 border border-slate-700 text-xs text-slate-200 rounded px-2 py-1"
                  value={selected?.status || "open"}
                  disabled={!selected || statusUpdating}
                  onChange={async (e) => {
                    if (!selected?.id) return;
                    const newStatus = e.target.value;
                    setStatusError(null);
                    try {
                      setStatusUpdating(true);
                      await updateFailureStatus(selected.id, newStatus);
                      const nextFailures = failures.map((f) =>
                        f.id === selected.id ? { ...f, status: newStatus } : f
                      );
                      setFailures(nextFailures);
                      setSelected({ ...selected, status: newStatus });
                      const statusCounts = nextFailures.reduce((acc, f) => {
                        const key = f.status || "open";
                        acc[key] = (acc[key] || 0) + 1;
                        return acc;
                      }, {});
                      setDashboard({
                        ...dashboard,
                        status_breakdown: Object.entries(statusCounts).map(([status, count]) => ({
                          status,
                          count,
                        })),
                      });
                    } catch (err) {
                      if (err?.response?.status === 401) {
                        navigate("/login");
                        return;
                      }
                      const detail = err?.response?.data?.detail;
                      setStatusError(
                        typeof detail === "string" ? detail : "Could not update status"
                      );
                    } finally {
                      setStatusUpdating(false);
                    }
                  }}
                >
                  {statusOptions.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
                {statusUpdating && (
                  <span className="text-[11px] text-slate-500">Updating...</span>
                )}
              </div>
              {statusError && (
                <div className="text-[11px] text-red-400 mt-1">{statusError}</div>
              )}
            </div>
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
              {!explainLoading && explainError && (
                <div className="text-[11px] text-amber-300/90 whitespace-pre-wrap">{explainError}</div>
              )}
              {!explainLoading && !explain && !explainError && (
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

      <RunChatPanel
        open={chatOpen}
        onClose={() => setChatOpen(false)}
        runId={runId}
        runName={activeRunName}
        selectedFailure={selected}
      />
      {!chatOpen && (
        <button
          type="button"
          aria-label="Open AI assistant"
          onClick={() => setChatOpen(true)}
          title={runId ? "Run assistant" : "Assistant — open a run to ask about failures"}
          className="fixed bottom-6 right-6 z-[90] flex items-center gap-2 rounded-full bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium px-4 py-3 shadow-xl border border-emerald-400/40"
        >
          AI
          <span className="text-emerald-200/90 text-xs font-normal">‹</span>
        </button>
      )}
    </div>
  );
};

export default Dashboard;
