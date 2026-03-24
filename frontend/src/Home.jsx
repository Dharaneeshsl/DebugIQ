import { useEffect, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { getRuns } from "./api/api";

const Home = () => {
  const [loading, setLoading] = useState(true);
  const [hasRuns, setHasRuns] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    const load = async () => {
      try {
        const res = await getRuns();
        if (res.data && res.data.length > 0) {
          setHasRuns(true);
          navigate(`/dashboard/${res.data[0].id}`);
          return;
        }
      } catch (err) {
        // fall back to upload
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [navigate]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="glass px-6 py-4 rounded-xl card-glow flex items-center gap-3">
          <div className="h-5 w-5 border-2 border-emerald-400 border-t-transparent rounded-full animate-spin" />
          <span className="text-slate-200 text-sm">Loading...</span>
        </div>
      </div>
    );
  }

  if (!hasRuns) {
    return (
      <div className="min-h-screen flex items-center justify-center px-6">
        <div className="w-full max-w-2xl glass rounded-2xl p-10 card-glow text-center">
          <div className="text-xs text-emerald-400 uppercase tracking-[0.2em] mono">DebugIQ</div>
          <h1 className="text-2xl font-semibold mt-2">Dashboard</h1>
          <p className="text-slate-400 mb-6">Upload your first regression log to generate the dashboard.</p>
          <Link to="/upload" className="inline-flex items-center justify-center bg-emerald-500 hover:bg-emerald-400 text-sm px-5 py-2 rounded">
            Upload Log
          </Link>
        </div>
      </div>
    );
  }

  return null;
};

export default Home;