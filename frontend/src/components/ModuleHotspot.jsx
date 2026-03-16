import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

const ModuleHotspot = ({ data }) => (
  <div className="glass rounded-xl p-4 card-glow">
    <h3 className="text-sm text-slate-300 mb-2">Module Hotspot Analysis</h3>
    <div className="h-56">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data}>
          <XAxis dataKey="module" stroke="#94a3b8" fontSize={11} />
          <YAxis stroke="#94a3b8" fontSize={11} />
          <Tooltip />
          <Bar dataKey="count" fill="#ef4444" radius={[6, 6, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  </div>
);

export default ModuleHotspot;