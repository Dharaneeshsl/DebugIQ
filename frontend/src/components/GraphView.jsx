import React, { useEffect, useRef, useState } from "react";
import ForceGraph2D from "react-force-graph-2d";

export default function GraphView({ nodes = [], edges = [] }) {
  const wrapRef = useRef(null);
  const [size, setSize] = useState({ w: 600, h: 360 });
  const graphData = { nodes, links: edges };

  useEffect(() => {
    if (!wrapRef.current) return;
    const ro = new ResizeObserver((entries) => {
      const rect = entries[0]?.contentRect;
      if (!rect) return;
      const w = Math.max(320, Math.floor(rect.width));
      const h = Math.max(260, Math.floor(rect.height));
      setSize({ w, h });
    });
    ro.observe(wrapRef.current);
    return () => ro.disconnect();
  }, []);

  return (
    <div className="glass rounded-xl p-4 card-glow">
      <h3 className="text-sm text-slate-300 mb-2">Failure Clustering & Root Cause Topology</h3>
      <div ref={wrapRef} className="h-64 lg:h-80">
        {nodes.length === 0 ? (
          <div className="h-full flex items-center justify-center text-xs text-slate-500">
            No topology data yet.
          </div>
        ) : (
          <ForceGraph2D
            graphData={graphData}
            width={size.w}
            height={size.h}
            backgroundColor="rgba(15, 23, 42, 0)"
            nodeLabel={(node) =>
              [
                `ID: ${node.id}`,
                node.name ? `Module: ${node.name}` : null,
                node.category ? `Category: ${node.category}` : null,
                node.severity ? `Severity: ${node.severity}` : null,
              ]
                .filter(Boolean)
                .join("\n")
            }
            nodeAutoColorBy="group"
            linkColor={() => "rgba(148, 163, 184, 0.5)"}
            linkDirectionalArrowLength={3.5}
            linkDirectionalArrowRelPos={1}
          />
        )}
      </div>
    </div>
  );
}
