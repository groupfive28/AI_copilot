import { Navigate, useLocation } from "react-router-dom";

import { useAuth } from "./AuthContext.jsx";

export default function RequireAdminAuth({ children }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return <div className="ops-loading">Loading…</div>;
  }

  if (!user) {
    return <Navigate to="/operations/login" state={{ from: location.pathname }} replace />;
  }

  return children;
}
