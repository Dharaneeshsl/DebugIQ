import { useMemo, useState } from "react";

const severityColors = {
  FATAL: "bg-red-500/20 text-red-300 border border-red-500/40",
  ERROR: "bg-orange-500/20 text-orange-300 border border-orange-500/40",
  WARNING: "bg-yellow-500/20 text-yellow-300 border border-yellow-500/40",
  INFO: "bg-slate-500/20 text-slate-200 border border-slate-500/40",
};

const FailurePriorityTable = ({ data, onSelect }) => {
  const [severityFilter, setSeverityFilter] = useState("ALL");
  const [moduleFilter, setModuleFilter] = useState("ALL");

  const modules = useMemo(() => Array.from(new Set(data.map(d => d.module))), [data]);

  const filtered = data.filter(d => {
    if (severityFilter !== "ALL" && d.severity !== severityFilter) return false;
    if (moduleFilter !== "ALL" && d.module !== moduleFilter) return false;
    return true;
  });

  return (
    <div className="glass rounded-xl p-4 card-glow">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 mb-3">
        <div>
          <h3 className="text-sm text-slate-300">Failure Priority Ranking</h3>
          <p className="text-xs text-slate-500">Sorted by DebugIQ score</p>
        </div>
        <div className="flex gap-2">
          <select value={severityFilter} onChange={(e) => setSeverityFilter(e.target.value)} className="bg-slate-900 text-white text-xs px-2 py-1 rounded border border-slate-700">
            <option value="ALL">All Severities</option>
            <option value="FATAL">FATAL</option>
            <option value="ERROR">ERROR</option>
            <option value="WARNING">WARNING</option>
            <option value="INFO">INFO</option>
          </select>
          <select value={moduleFilter} onChange={(e) => setModuleFilter(e.target.value)} className="bg-slate-900 text-white text-xs px-2 py-1 rounded border border-slate-700">
            <option value="ALL">All Modules</option>
            {modules.map(m => <option key={m} value={m}>{m}</option>)}
          </select>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-slate-400">
            <tr className="border-b border-slate-700/60">
              <th className="text-left py-2">Rank</th>
              <th className="text-left py-2">Severity</th>
              <th className="text-left py-2">Module</th>
              <th className="text-left py-2">Category</th>
              <th className="text-left py-2">Score</th>
              <th className="text-left py-2">Freq</th>
              <th className="text-left py-2">Action</th>
            </tr>
          </thead>
          <tbody>
            {filtered.slice(0, 15).map((row) => (
              <tr key={row.rank} className="border-b border-slate-800/60 hover:bg-slate-800/40 transition">
                <td className="py-2">{row.rank}</td>
                <td className="py-2">
                  <span className={`px-2 py-1 rounded text-xs ${severityColors[row.severity] || "bg-slate-500/20"}`}>{row.severity}</span>
                </td>
                <td className="py-2 mono text-emerald-200/90">{row.module}</td>
                <td className="py-2">{row.category}</td>
                <td className="py-2">{row.score.toFixed(2)}</td>
                <td className="py-2">{row.frequency}</td>
                <td className="py-2">
                  <button onClick={() => onSelect(row)} className="text-emerald-300 hover:text-emerald-200">Analyze</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default FailurePriorityTable;