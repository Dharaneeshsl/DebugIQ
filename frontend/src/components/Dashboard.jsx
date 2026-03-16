import { useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { getDashboard, getFailures, exportCSV, uploadLog } from "../api/api";
import HealthScore from "./HealthScore";
import CategoryDistribution from "./CategoryDistribution";
import FailurePriorityTable from "./FailurePriorityTable";
import ModuleHotspot from "./ModuleHotspot";
import FailureClusters from "./FailureClusters";
import FailureTimeline from "./FailureTimeline";
import RootCauseSuggestion from "./RootCauseSuggestion";

const Dashboard = () => {
  const { runId } = useParams();
  const navigate = useNavigate();
  const [dashboard, setDashboard] = useState(null);
  const [failures, setFailures] = useState([]);
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

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
        setError(err?.response?.data?.detail || "Failed to load dashboard");
      } finally {
        setLoading(false);
      }
    };
    fetchAll();
  }, [runId]);

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
        </div>

        <div className="glass rounded-xl p-4 text-sm text-slate-300">
          <div className="text-xs text-slate-500 mb-2">Run ID</div>
          <div className="mono text-emerald-300">{runId ? `#${runId}` : "No run loaded"}</div>
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
          </div>
        </section>

        <section className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
          <FailureClusters data={dashboard.failure_clusters} />
          <FailureTimeline data={dashboard.failure_timeline} />
        </section>

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