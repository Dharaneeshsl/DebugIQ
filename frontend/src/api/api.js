import axios from "axios";

const BASE =
  import.meta.env.VITE_API_BASE_URL ||
  (import.meta.env.PROD ? "/api" : "http://localhost:8000");

const client = axios.create({
  baseURL: BASE,
});

client.interceptors.request.use((config) => {
  const token = localStorage.getItem("debugiq_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
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
export const getFailures = (runId, { limit, offset } = {}) =>
  client.get(`/failures/${runId}`, { params: { limit, offset } });
export const getRuns = ({ limit, offset } = {}) =>
  client.get(`/runs`, { params: { limit, offset } });
export const deduplicateLogs = (logs, similarity_threshold = 0.9) =>
  client.post(`/deduplicate`, { logs, similarity_threshold });
export const prioritizeFailures = (feedback) =>
  client.post(`/prioritize`, { feedback });
export const getRootCause = (runId, failureId) =>
  client.get(`/root-cause/${runId}/${failureId}`);
export const getExplanation = (runId, failureId) =>
  client.get(`/explain/${runId}/${failureId}`);
export const logout = () => client.post(`/logout`);

export const login = async (username, password) => {
  const body = new URLSearchParams();
  body.append("username", username);
  body.append("password", password);
  const res = await client.post(`/token`, body, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
  if (res?.data?.access_token) {
    localStorage.setItem("debugiq_token", res.data.access_token);
  }
  return res;
};

export const signup = async (username, password, role) => {
  const res = await client.post(`/signup`, { username, password, role });
  if (res?.data?.access_token) {
    localStorage.setItem("debugiq_token", res.data.access_token);
  }
  return res;
};

export const getAdminExists = () => client.get(`/auth/admin-exists`);

export const exportCSV = (runId) => {
  window.open(`${BASE}/report/${runId}?format=csv`, "_blank");
};

export default client;
