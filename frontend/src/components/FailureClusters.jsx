import { ScatterChart, Scatter, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

const FailureClusters = ({ data }) => (
  <div className="glass rounded-xl p-4 card-glow">
    <h3 className="text-sm text-slate-300 mb-2">Failure Clusters</h3>
    <div className="h-56">
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart>
          <XAxis dataKey="x" stroke="#94a3b8" fontSize={11} />
          <YAxis dataKey="y" stroke="#94a3b8" fontSize={11} />
          <Tooltip />
          <Scatter data={data} fill="#38bdf8" />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  </div>
);

export default FailureClusters;