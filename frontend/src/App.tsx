import { NavLink, Route, Routes } from "react-router-dom";
import Chat from "./pages/Chat";
import Dashboard from "./pages/Dashboard";
import Schema from "./pages/Schema";
import HealthBadge from "./components/HealthBadge";

export default function App() {
  return (
    <div className="app">
      <nav className="nav">
        <div className="nav-brand">HouseDataBrowser</div>
        <div className="nav-links">
          <NavLink to="/" end>Chat</NavLink>
          <NavLink to="/dashboard">Dashboard</NavLink>
          <NavLink to="/schema">Schema</NavLink>
        </div>
        <HealthBadge />
      </nav>
      <main className="main">
        <Routes>
          <Route path="/" element={<Chat />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/schema" element={<Schema />} />
        </Routes>
      </main>
    </div>
  );
}
