const RootCauseSuggestion = ({ suggestion, recommendation }) => (
  <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
    <div className="glass rounded-xl p-4 card-glow">
      <h3 className="text-sm text-slate-300 mb-2">Root Cause Suggestion</h3>
      <p className="text-slate-200 text-sm">{suggestion || "Select a failure to see suggestions."}</p>
    </div>
    <div className="glass rounded-xl p-4 card-glow">
      <h3 className="text-sm text-slate-300 mb-2">Debug Recommendation</h3>
      <p className="text-slate-200 text-sm">{recommendation || "Select a failure to see recommendations."}</p>
    </div>
  </div>
);

export default RootCauseSuggestion;