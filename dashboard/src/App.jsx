import { Link, Route, Routes } from "react-router-dom";
import ReportList from "./pages/ReportList.jsx";
import ReportDetail from "./pages/ReportDetail.jsx";

export default function App() {
  return (
    <div className="app">
      <header className="topbar">
        <div className="topbar-inner">
          <div className="brand-block">
            <Link to="/" className="brand">
              Loggy AI
            </Link>
            <span className="brand-tag">Operations</span>
          </div>
          <nav className="topnav">
            <Link to="/" className="topnav-link active">
              Incidents
            </Link>
          </nav>
        </div>
      </header>
      <main className="main">
        <Routes>
          <Route path="/" element={<ReportList />} />
          <Route path="/reports/:id" element={<ReportDetail />} />
        </Routes>
      </main>
    </div>
  );
}
