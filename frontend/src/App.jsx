import { Suspense, lazy } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

const LogUpload = lazy(() => import("./components/LogUpload"));
const Dashboard = lazy(() => import("./components/Dashboard"));
const Login = lazy(() => import("./components/Login"));
const Signup = lazy(() => import("./components/Signup"));

const RequireAuth = ({ children }) => {
  const token = localStorage.getItem("debugiq_token");
  if (!token) {
    return <Navigate to="/login" replace />;
  }
  return children;
};

/** Logged-in users should not see sign-in / sign-up screens */
const RequireGuest = ({ children }) => {
  const token = localStorage.getItem("debugiq_token");
  if (token) {
    return <Navigate to="/dashboard" replace />;
  }
  return children;
};

/** Unknown paths: send guests to login, authenticated users to dashboard */
const DefaultRedirect = () => {
  const token = localStorage.getItem("debugiq_token");
  return <Navigate to={token ? "/dashboard" : "/login"} replace />;
};

const App = () => (
  <BrowserRouter
    future={{
      v7_startTransition: true,
      v7_relativeSplatPath: true,
    }}
  >
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center bg-slate-950 text-slate-200">
          <div className="flex items-center gap-3 rounded-xl border border-slate-800 bg-slate-900/80 px-5 py-3">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-emerald-400 border-t-transparent" />
            <span className="text-sm">Loading DebugIQ...</span>
          </div>
        </div>
      }
    >
      <Routes>
        <Route path="/" element={<Navigate to="/login" replace />} />
        <Route
          path="/upload"
          element={
            <RequireAuth>
              <LogUpload />
            </RequireAuth>
          }
        />
        <Route
          path="/dashboard"
          element={
            <RequireAuth>
              <Dashboard />
            </RequireAuth>
          }
        />
        <Route
          path="/dashboard/:runId"
          element={
            <RequireAuth>
              <Dashboard />
            </RequireAuth>
          }
        />
        <Route
          path="/login"
          element={
            <RequireGuest>
              <Login />
            </RequireGuest>
          }
        />
        <Route
          path="/signup"
          element={
            <RequireGuest>
              <Signup />
            </RequireGuest>
          }
        />
        <Route path="*" element={<DefaultRedirect />} />
      </Routes>
    </Suspense>
  </BrowserRouter>
);

export default App;
