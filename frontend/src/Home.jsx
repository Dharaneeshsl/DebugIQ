import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getRuns } from "./api/api";
import { Link } from "react-router-dom";

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
      <div className="min-h-screen bg-base text-white flex items-center justify-center">
        <div className="flex items-center gap-3">
          <div className="h-5 w-5 border-2 border-emerald-400 border-t-transparent rounded-full animate-spin" />
          <span className="text-slate-300 text-sm">Loading...</span>
        </div>
      </div>
    );
  }

  if (!hasRuns) {
    return (
      <div className="min-h-screen bg-base text-white flex items-center justify-center px-6">
        <div className="w-full max-w-2xl bg-panel border border-slate-700/40 rounded-2xl p-8 text-center">
          <h1 className="text-2xl font-semibold mb-2">DebugIQ Dashboard</h1>
          <p className="text-slate-400 mb-6">
            No runs yet. Upload a regression log to generate your first dashboard.
          </p>
          <Link
            to="/upload"
            className="inline-flex items-center justify-center bg-emerald-500 hover:bg-emerald-400 text-sm px-5 py-2 rounded"
          >
            Upload Log
          </Link>
        </div>
      </div>
    );
  }

  return null;
};

export default Home;
