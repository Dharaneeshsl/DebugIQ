import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

const ModuleHotspot = ({ data }) => (
  <div className="bg-card border border-slate-700/40 rounded-xl p-4">
    <h3 className="text-sm text-slate-300 mb-2">Module Hotspot Analysis</h3>
    <div className="h-56">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data}>
          <XAxis dataKey="module" stroke="#94a3b8" fontSize={11} />
          <YAxis stroke="#94a3b8" fontSize={11} />
          <Tooltip />
          <Bar dataKey="count" fill="#f97316" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  </div>
);

export default ModuleHotspot;