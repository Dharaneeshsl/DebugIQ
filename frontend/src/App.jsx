import { BrowserRouter, Routes, Route } from "react-router-dom";
import LogUpload from "./components/LogUpload";
import Dashboard from "./components/Dashboard";

const App = () => (
  <BrowserRouter
    future={{
      v7_startTransition: true,
      v7_relativeSplatPath: true,
    }}
  >
    <Routes>
      <Route path="/" element={<Dashboard />} />
      <Route path="/upload" element={<LogUpload />} />
      <Route path="/dashboard/:runId" element={<Dashboard />} />
    </Routes>
  </BrowserRouter>
);

export default App;
