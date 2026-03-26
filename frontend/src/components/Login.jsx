import { useEffect, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { login } from "../api/api";

const Login = () => {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    const token = localStorage.getItem("debugiq_token");
    if (token) navigate("/");
  }, []);

  const onSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(username, password);
      navigate("/");
    } catch (err) {
      setError(err?.response?.data?.detail || "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-6">
      <div className="w-full max-w-md glass rounded-2xl p-10 card-glow">
        <div className="text-xs text-emerald-400 uppercase tracking-[0.2em] mono">DebugIQ</div>
        <h1 className="text-2xl font-semibold mt-2">Sign in</h1>
        <p className="text-slate-400 text-sm mt-1">Use your credentials to access DebugIQ.</p>

        <form onSubmit={onSubmit} className="mt-6 space-y-4">
          <div>
            <label className="block text-sm text-slate-300 mb-2">Username</label>
            <input
              className="w-full bg-slate-900/40 border border-slate-700 rounded px-3 py-2 text-slate-200"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
            />
          </div>
          <div>
            <label className="block text-sm text-slate-300 mb-2">Password</label>
            <input
              type="password"
              className="w-full bg-slate-900/40 border border-slate-700 rounded px-3 py-2 text-slate-200"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
            />
          </div>

          <button
            disabled={loading}
            className="w-full bg-emerald-500 hover:bg-emerald-400 text-sm px-3 py-2 rounded disabled:opacity-50"
          >
            {loading ? "Signing in..." : "Sign in"}
          </button>

          {error && <div className="text-red-400 text-sm">{error}</div>}
        </form>

        <div className="mt-4 text-sm text-slate-400">
          New here?{" "}
          <Link className="text-emerald-400 hover:text-emerald-300" to="/signup">
            Create an account
          </Link>
        </div>
      </div>
    </div>
  );
};

export default Login;

