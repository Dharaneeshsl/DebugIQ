const HealthScore = ({ score }) => {
  const color = score < 40 ? "text-red-400" : score < 70 ? "text-yellow-400" : "text-emerald-400";
  return (
    <div className="bg-card border border-slate-700/40 rounded-xl p-4 flex flex-col items-start">
      <div className="text-sm text-slate-400">Health Score</div>
      <div className={`text-3xl font-semibold ${color}`}>{score}</div>
    </div>
  );
};

export default HealthScore;