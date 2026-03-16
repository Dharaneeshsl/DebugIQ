import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { getDashboard, getFailures, exportCSV } from "../api/api";
import HealthScore from "./HealthScore";
import CategoryDistribution from "./CategoryDistribution";
import FailurePriorityTable from "./FailurePriorityTable";
import ModuleHotspot from "./ModuleHotspot";
import FailureClusters from "./FailureClusters";
import FailureTimeline from "./FailureTimeline";
import RootCauseSuggestion from "./RootCauseSuggestion";

const Dashboard = () => {
  const { runId } = useParams();
  const [dashboard, setDashboard] = useState(null);
  const [failures, setFailures] = useState([]);
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
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
      <div className="min-h-screen bg-base text-white flex items-center justify-center">
        <div className="flex items-center gap-3">
          <div className="h-5 w-5 border-2 border-emerald-400 border-t-transparent rounded-full animate-spin" />
          <span className="text-slate-300 text-sm">Loading dashboard...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return <div className="min-h-screen bg-base text-red-400 flex items-center justify-center">{error}</div>;
  }

  const suggestion = dashboard.root_cause_suggestions.find((s) => s.failure_id === selected?.id)?.suggestion;
  const recommendation = dashboard.debug_recommendations.find((r) => r.failure_id === selected?.id)?.recommendation;

  return (
    <div className="min-h-screen bg-base text-white px-6 py-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold">DebugIQ Dashboard</h1>
          <p className="text-slate-400 text-sm">Run ID: {runId}</p>
        </div>
        <button onClick={() => exportCSV(runId)} className="bg-emerald-500 hover:bg-emerald-400 text-sm px-4 py-2 rounded">
          Export CSV
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <HealthScore score={dashboard.health_score} />
        <div className="bg-card border border-slate-700/40 rounded-xl p-4">
          <div className="text-sm text-slate-400">Total Failures</div>
          <div className="text-2xl font-semibold">{dashboard.total_failures}</div>
        </div>
        <div className="bg-card border border-slate-700/40 rounded-xl p-4">
          <div className="text-sm text-slate-400">Unique Failures</div>
          <div className="text-2xl font-semibold">{dashboard.unique_failures}</div>
        </div>
        <div className="bg-card border border-slate-700/40 rounded-xl p-4">
          <div className="text-sm text-slate-400">Critical Issues</div>
          <div className="text-2xl font-semibold text-red-400">{dashboard.critical_count}</div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
        <CategoryDistribution data={dashboard.category_distribution} />
        <ModuleHotspot data={dashboard.module_hotspots} />
      </div>

      <FailurePriorityTable data={dashboard.priority_ranking} onSelect={(row) => {
        const match = failures.find((f) => f.unique_failure_id === row.unique_failure_id) || failures[0];
        setSelected(match);
      }} />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 my-6">
        <FailureClusters data={dashboard.failure_clusters} />
        <FailureTimeline data={dashboard.failure_timeline} />
      </div>

      <RootCauseSuggestion suggestion={suggestion} recommendation={recommendation} />
    </div>
  );
};

export default Dashboard;
