import axios from "axios";

const BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

const client = axios.create({
  baseURL: BASE,
});

export const uploadLog = (file, onProgress) => {
  const formData = new FormData();
  formData.append("file", file);
  return client.post("/upload", formData, {
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress: (evt) => {
      if (onProgress && evt.total) {
        onProgress(Math.round((evt.loaded / evt.total) * 100));
      }
    },
  });
};

export const getDashboard = (runId) => client.get(`/dashboard/${runId}`);
export const getFailures = (runId) => client.get(`/failures/${runId}`);
export const getRuns = () => client.get(`/runs`);
export const exportCSV = (runId) => {
  window.open(`${BASE}/report/${runId}?format=csv`, "_blank");
};

export default client;