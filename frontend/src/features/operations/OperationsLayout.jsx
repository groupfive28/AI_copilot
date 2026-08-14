import { Link, NavLink, Outlet } from "react-router-dom";

import "./operations.css";

export default function OperationsLayout() {
  return (
    <div className="ops-root">
      <aside className="ops-sidebar">
        <div className="ops-sidebar-brand">Penta Operations</div>
        <nav className="ops-sidebar-nav">
          <NavLink to="/operations" end className={({ isActive }) => `ops-nav-link ${isActive ? "active" : ""}`}>
            Applications
          </NavLink>
          <NavLink
            to="/operations/verification-results"
            className={({ isActive }) => `ops-nav-link ${isActive ? "active" : ""}`}
          >
            Verification Results
          </NavLink>
        </nav>
        <div className="ops-sidebar-footer">
          <Link to="/onboarding" className="ops-nav-link">
            ← Onboarding flow
          </Link>
        </div>
      </aside>
      <main className="ops-main">
        <Outlet />
      </main>
    </div>
  );
}
