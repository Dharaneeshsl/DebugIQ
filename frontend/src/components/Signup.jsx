import { useEffect, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { signup, getAdminExists } from "../api/api";

const Signup = () => {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("user");
  const [adminExists, setAdminExists] = useState(false);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    const load = async () => {
      try {
        const res = await getAdminExists();
        setAdminExists(Boolean(res?.data?.admin_exists));
        if (res?.data?.admin_exists) {
          setRole("user");
        }
      } catch {
        setAdminExists(false);
      }
    };
    load();
  }, []);

  const onSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await signup(username, password, role);
      navigate("/dashboard");
    } catch (err) {
      setError(err?.response?.data?.detail || "Sign up failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-6">
      <div className="w-full max-w-md glass rounded-2xl p-10 card-glow">
        <div className="text-xs text-emerald-400 uppercase tracking-[0.2em] mono">DebugIQ</div>
        <h1 className="text-2xl font-semibold mt-2">Sign up</h1>
        <p className="text-slate-400 text-sm mt-1">
          Create your account to access DebugIQ.
        </p>

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
              autoComplete="new-password"
            />
          </div>

          <div>
            <label className="block text-sm text-slate-300 mb-2">Role</label>
            <div className="flex gap-3">
              <label className="flex items-center gap-2 text-sm text-slate-300">
                <input
                  type="radio"
                  name="role"
                  value="user"
                  checked={role === "user"}
                  onChange={() => setRole("user")}
                />
                User
              </label>
              <label className={`flex items-center gap-2 text-sm ${adminExists ? "text-slate-500" : "text-slate-300"}`}>
                <input
                  type="radio"
                  name="role"
                  value="admin"
                  checked={role === "admin"}
                  onChange={() => setRole("admin")}
                  disabled={adminExists}
                />
                Admin
              </label>
            </div>
            {adminExists && (
              <div className="text-xs text-slate-500 mt-2">
                An admin already exists. Sign up as a user.
              </div>
            )}
          </div>

          <button
            disabled={loading}
            className="w-full bg-emerald-500 hover:bg-emerald-400 text-sm px-3 py-2 rounded disabled:opacity-50"
          >
            {loading ? "Creating account..." : "Sign up"}
          </button>

          {error && <div className="text-red-400 text-sm">{error}</div>}
        </form>

        <div className="mt-4 text-sm text-slate-400">
          Already have an account?{" "}
          <Link className="text-emerald-400 hover:text-emerald-300" to="/login">
            Sign in
          </Link>
        </div>
      </div>
    </div>
  );
};

export default Signup;
