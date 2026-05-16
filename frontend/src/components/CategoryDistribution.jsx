import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";

const COLORS = {
  uvm_fatal: "#dc2626",
  uvm_error: "#ef4444",
  uvm_warning: "#f97316",
  uvm_phase_error: "#eab308",
  uvm_sequence_error: "#84cc16",
  uvm_scoreboard_mismatch: "#06b6d4",
  sva_assertion_failure: "#8b5cf6",
  assertion_failure: "#ec4899",
  timeout_error: "#f59e0b",
  protocol_violation: "#a855f7",
  data_mismatch: "#10b981",
  memory_error: "#3b82f6",
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
