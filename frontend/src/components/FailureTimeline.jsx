import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

const formatTime = (t) => {
  if (!t) return "";
  const s = String(t);
  if (s.includes("T")) {
    const part = s.split("T")[1] || s;
    return part.slice(0, 8);
  }
  return s.slice(0, 8);
};

const FailureTimeline = ({ data }) => (
  <div className="glass rounded-xl p-4 card-glow">
    <h3 className="text-sm text-slate-300 mb-2">Failure Timeline</h3>
    <div className="h-56">
      {data?.length ? (
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <XAxis dataKey="time" stroke="#94a3b8" fontSize={11} tickFormatter={formatTime} />
            <YAxis stroke="#94a3b8" fontSize={11} />
            <Tooltip />
            <Line type="monotone" dataKey="count" stroke="#eab308" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      ) : (
        <div className="h-full flex items-center justify-center text-xs text-slate-500">
          No timeline data yet.
        </div>
      )}
    </div>
  </div>
);

export default FailureTimeline;
