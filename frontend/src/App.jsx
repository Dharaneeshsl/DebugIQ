import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import LogUpload from "./components/LogUpload";
import Dashboard from "./components/Dashboard";
import Login from "./components/Login";
import Signup from "./components/Signup";

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
  </BrowserRouter>
);

export default App;
