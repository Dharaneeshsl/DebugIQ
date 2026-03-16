import { BrowserRouter, Routes, Route } from "react-router-dom";
import LogUpload from "./components/LogUpload";
import Dashboard from "./components/Dashboard";

const App = () => (
  <BrowserRouter>
    <Routes>
      <Route path="/" element={<LogUpload />} />
      <Route path="/dashboard/:runId" element={<Dashboard />} />
    </Routes>
  </BrowserRouter>
);

export default App;