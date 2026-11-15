import { useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { uploadLog } from "../api/api";

const LogUpload = () => {
  const [dragging, setDragging] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const uploading = useRef(false);
  const navigate = useNavigate();

  const handleUpload = async (file) => {
    if (uploading.current) return;
    if (!/\.(log|txt|gz)$/i.test(file.name) || !file.size || file.size > 20 * 1024 * 1024) {
      setError("Choose a non-empty .log, .txt, or .gz file up to 20 MB.");
      return;
    }
    uploading.current = true;
    setBusy(true);
    setError(null);
    setProgress(0);
    try {
      const res = await uploadLog(file, setProgress);
      navigate(`/dashboard/${res.data.run_id}`);
    } catch (err) {
      if (err?.response?.status === 401) {
        navigate("/login");
        return;
      }
      setError(err?.response?.data?.detail || "Upload failed");
    } finally {
      uploading.current = false;
      setBusy(false);
    }
  };

  const onDrop = (evt) => {
    evt.preventDefault();
    setDragging(false);
    const file = evt.dataTransfer.files?.[0];
    if (file) handleUpload(file);
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-6">
      <div className="w-full max-w-2xl glass rounded-2xl p-10 card-glow">
        <div className="flex items-center justify-between mb-6">
          <div>
            <div className="text-xs text-emerald-400 uppercase tracking-[0.2em] mono">DebugIQ</div>
            <h1 className="text-2xl font-semibold">Upload Regression Log</h1>
            <p className="text-slate-400 text-sm mt-1">Drop .log, .txt or .gz to generate a dashboard</p>
          </div>
          <div className="text-xs text-slate-500">Pipeline v2</div>
        </div>

        <div
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className={`border-2 border-dashed rounded-xl p-10 text-center transition ${dragging ? "border-emerald-400 bg-emerald-400/10" : "border-slate-600"}`}
        >
          <input
            type="file"
            disabled={busy}
            accept=".log,.txt,.gz"
            onChange={(e) => { const file = e.target.files?.[0]; e.target.value = ""; if (file) handleUpload(file); }}
            className="hidden"
            id="file-input"
          />
          <label htmlFor="file-input" className="cursor-pointer">
            <div className="text-lg font-medium">{busy ? "Analyzing your log…" : "Drag & drop or click to select"}</div>
            <div className="text-slate-400 text-sm mt-1">Supports .log, .txt, .gz</div>
          </label>
        </div>

        {progress > 0 && (
          <div className="mt-6">
            <div className="h-2 bg-slate-800 rounded">
              <div className="h-2 bg-emerald-500 rounded" style={{ width: `${progress}%` }} />
            </div>
            <div className="text-xs text-slate-400 mt-2">{progress}%</div>
          </div>
        )}

        {error && <div role="alert" className="mt-4 text-red-400 text-sm">{error}</div>}
        <Link to="/dashboard" className="inline-block mt-6 text-sm text-slate-400">Back to dashboard</Link>
      </div>
    </div>
  );
};

export default LogUpload;
