import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";

const COLORS = {
  assertion_failure: "#ef4444",
  data_mismatch: "#f97316",
  timeout_error: "#eab308",
  protocol_violation: "#8b5cf6",
  memory_error: "#06b6d4",
};

const CategoryDistribution = ({ data }) => (
  <div className="glass rounded-xl p-4 card-glow">
    <h3 className="text-sm text-slate-300 mb-2">Failure Category Distribution</h3>
    <div className="h-56">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie dataKey="count" data={data} innerRadius={50} outerRadius={80}>
            {data.map((entry, idx) => (
              <Cell key={idx} fill={COLORS[entry.category] || "#64748b"} />
            ))}
          </Pie>
          <Tooltip />
        </PieChart>
      </ResponsiveContainer>
    </div>
  </div>
);

export default CategoryDistribution;