/**
 * Per-module efficiency for this run: smaller share of total failure rows → higher %.
 * efficiency = 100 × (1 − module_error_count / total_failure_rows_in_run)
 * Note: one module owning 100% of rows ⇒ 0% (hotspot); color reflects that (not “good”).
 */
function efficiencyTier(pct) {
  if (pct >= 67) {
    return {
      text: "text-emerald-300/90",
      bar: "bg-gradient-to-r from-emerald-800 to-emerald-400",
    };
  }
  if (pct >= 34) {
    return {
      text: "text-amber-300/90",
      bar: "bg-gradient-to-r from-amber-800 to-amber-400",
    };
  }
  return {
    text: "text-rose-300/90",
    bar: "bg-gradient-to-r from-rose-900 to-rose-500",
  };
}

const ModuleEfficiency = ({ data }) => {
  const rows = Array.isArray(data) ? data : [];
  if (!rows.length) {
    return (
      <div className="glass rounded-xl p-4 card-glow">
        <h3 className="text-sm text-slate-300 mb-1">Module efficiency</h3>
        <div className="text-xs text-slate-500">No module data yet.</div>
      </div>
    );
  }

  return (
    <div className="glass rounded-xl p-4 card-glow">
      <h3 className="text-sm text-slate-300 mb-0.5">Module efficiency</h3>
      <p className="text-[11px] text-slate-500 mb-3 leading-relaxed">
        Share of all failure rows in this run (same rows as Hotspot). High % = small share; 0% = that module
        accounts for every failure row.
      </p>
      <div className="max-h-56 overflow-y-auto pr-1 space-y-2">
        {rows.map((row) => {
          const eff = Number(row.efficiency);
          const pct = Number.isFinite(eff) ? Math.min(100, Math.max(0, eff)) : 0;
          const tier = efficiencyTier(pct);
          return (
            <div key={row.module}>
              <div className="flex justify-between text-[11px] text-slate-400 mb-0.5">
                <span className="font-mono text-slate-200/90 truncate max-w-[55%]" title={row.module}>
                  {row.module}
                </span>
                <span>
                  <span className="text-slate-500">{row.error_count} err · </span>
                  <span className={`tabular-nums ${tier.text}`}>{pct}%</span>
                </span>
              </div>
              <div className="h-1.5 rounded-full bg-slate-800 overflow-hidden">
                <div
                  className={`h-full rounded-full transition-[width] ${tier.bar}`}
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default ModuleEfficiency;
