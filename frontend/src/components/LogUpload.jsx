import { useCallback, useState } from "react";
import { useNavigate } from "react-router-dom";
import { uploadLog } from "../api/api";

const LogUpload = () => {
  const [dragging, setDragging] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  const handleUpload = async (file) => {
    setError(null);
    setProgress(0);
    try {
      const res = await uploadLog(file, setProgress);
      navigate(`/dashboard/${res.data.run_id}`);
    } catch (err) {
      setError(err?.response?.data?.detail || "Upload failed");
    }
  };

  const onDrop = useCallback((evt) => {
    evt.preventDefault();
    setDragging(false);
    const file = evt.dataTransfer.files?.[0];
    if (file) handleUpload(file);
  }, []);

  return (
    <div className="min-h-screen bg-base text-white flex items-center justify-center px-6">
      <div className="w-full max-w-xl bg-panel border border-slate-700/40 rounded-2xl p-8">
        <h1 className="text-2xl font-semibold mb-2">DebugIQ Log Upload</h1>
        <p className="text-slate-400 mb-6">Upload .log, .txt or .gz regression logs</p>

        <div
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className={`border-2 border-dashed rounded-xl p-8 text-center transition ${dragging ? "border-emerald-400 bg-emerald-400/10" : "border-slate-600"}`}
        >
          <input
            type="file"
            accept=".log,.txt,.gz"
            onChange={(e) => e.target.files?.[0] && handleUpload(e.target.files[0])}
            className="hidden"
            id="file-input"
          />
          <label htmlFor="file-input" className="cursor-pointer">
            <div className="text-lg font-medium">Drag & drop or click to select</div>
            <div className="text-slate-400 text-sm mt-1">Supports .log, .txt, .gz</div>
          </label>
        </div>

        {progress > 0 && (
          <div className="mt-4">
            <div className="h-2 bg-slate-700 rounded">
              <div className="h-2 bg-emerald-500 rounded" style={{ width: `${progress}%` }} />
            </div>
            <div className="text-xs text-slate-400 mt-1">{progress}%</div>
          </div>
        )}

        {error && <div className="mt-4 text-red-400 text-sm">{error}</div>}
      </div>
    </div>
  );
};

export default LogUpload;