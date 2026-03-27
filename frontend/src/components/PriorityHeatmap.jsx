import React from "react";

export default function PriorityHeatmap({ xLabels = [], yLabels = [], data = [] }) {
  if (!data.length) {
    return (
      <div className="glass rounded-xl p-4 card-glow">
        <h3 className="text-sm text-slate-300 mb-2">Severity vs Module Hotspots</h3>
        <div className="text-xs text-slate-500">No hotspot data yet.</div>
      </div>
    );
  }

  const flat = data.flat().map((v) => Number(v) || 0);
  const max = Math.max(...flat, 0);
  const intensity = (value) => {
    if (max <= 0) return 0;
    return Math.max(0.08, value / max);
  };

  return (
    <div className="glass rounded-xl p-4 card-glow">
      <h3 className="text-sm text-slate-300 mb-2">Severity vs Module Hotspots</h3>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] border-separate border-spacing-0 text-xs">
          <thead>
            <tr>
              <th className="text-left text-slate-400 px-3 py-2 w-[140px]">Module</th>
              {xLabels.map((label) => (
                <th key={label} className="text-center text-slate-300 px-3 py-2 min-w-[100px]">
                  {label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {yLabels.map((rowLabel, rIdx) => (
              <tr key={rowLabel}>
                <td className="text-slate-300 px-3 py-3 border border-slate-700/40 bg-slate-900/30">
                  {rowLabel}
                </td>
                {xLabels.map((_, cIdx) => {
                  const value = Number(data?.[rIdx]?.[cIdx] ?? 0);
                  const alpha = intensity(value);
                  return (
                    <td
                      key={`${rowLabel}-${cIdx}`}
                      className="text-center px-3 py-3 border border-slate-700/40 font-medium"
                      style={{
                        backgroundColor: `rgba(220, 38, 38, ${alpha})`,
                        color: value > 0 ? "#0f172a" : "#94a3b8",
                      }}
                    >
                      {value}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
