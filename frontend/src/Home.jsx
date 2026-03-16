import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getRuns } from "./api/api";
import LogUpload from "./components/LogUpload";

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
    return <LogUpload />;
  }

  return null;
};

export default Home;