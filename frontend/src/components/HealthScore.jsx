const HealthScore = ({ score }) => {
  const color = score < 40 ? "text-red-400" : score < 70 ? "text-yellow-400" : "text-emerald-400";
  return (
    <div className="glass rounded-xl p-4 card-glow">
      <div className="text-xs text-slate-400">Health Score</div>
      <div className={`text-3xl font-semibold mt-2 ${color}`}>{score}</div>
      <div className="text-xs text-slate-500 mt-1">0-100 scale</div>
    </div>
  );
};

export default HealthScore;