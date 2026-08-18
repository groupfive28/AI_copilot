import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";

import { signOutAdmin } from "../../shared/firebase/client.js";
import { useAuth } from "./AuthContext.jsx";
import "./operations.css";

export default function OperationsLayout() {
  const { user } = useAuth();
  const navigate = useNavigate();

  async function handleSignOut() {
    await signOutAdmin();
    navigate("/operations/login", { replace: true });
  }

  return (
    <div className="ops-root">
      <aside className="ops-sidebar">
        <div className="ops-sidebar-brand">Penta Bank Operations</div>
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
          {user?.email && <div className="ops-sidebar-user">{user.email}</div>}
          <button type="button" className="ops-nav-link ops-nav-button" onClick={handleSignOut}>
            Sign out
          </button>
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
