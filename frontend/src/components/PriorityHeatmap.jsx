import React from "react";
import HeatMap from "react-heatmap-grid";

export default function PriorityHeatmap({ xLabels = [], yLabels = [], data = [] }) {
  if (!data.length) {
    return (
      <div className="glass rounded-xl p-4 card-glow">
        <h3 className="text-sm text-slate-300 mb-2">Severity vs Module Hotspots</h3>
        <div className="text-xs text-slate-500">No hotspot data yet.</div>
      </div>
    );
  }
  return (
    <div className="glass rounded-xl p-4 card-glow">
      <h3 className="text-sm text-slate-300 mb-2">Severity vs Module Hotspots</h3>
      <div style={{ fontSize: "12px", overflowX: "auto" }}>
        <HeatMap
          xLabels={xLabels}
          yLabels={yLabels}
          data={data}
          squares
          height={36}
          xLabelsStyle={() => ({
            color: "#94a3b8",
            fontSize: "11px",
            paddingBottom: "6px",
          })}
          yLabelsStyle={() => ({
            color: "#94a3b8",
            fontSize: "11px",
            paddingRight: "8px",
          })}
          cellStyle={(background, value, min, max) => ({
            background: `rgba(220, 38, 38, ${1 - (max - value) / (max - min || 1)})`,
            fontSize: "11px",
            color: "#0f172a",
          })}
          cellRender={(value) => <div>{value ?? 0}</div>}
        />
      </div>
    </div>
  );
}
