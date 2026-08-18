import { useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import { signInAdmin } from "../../shared/firebase/client.js";
import { useAuth } from "./AuthContext.jsx";
import "./operations.css";

const ERROR_MESSAGES = {
  "auth/invalid-credential": "Incorrect email or password.",
  "auth/invalid-email": "That doesn't look like a valid email address.",
  "auth/too-many-requests": "Too many attempts - wait a moment and try again.",
  "auth/user-disabled": "This account has been disabled.",
};

export default function LoginPage() {
  const { user, loading } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  if (!loading && user) {
    const redirectTo = location.state?.from ?? "/operations";
    return <Navigate to={redirectTo} replace />;
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await signInAdmin(email.trim(), password);
      navigate(location.state?.from ?? "/operations", { replace: true });
    } catch (err) {
      setError(ERROR_MESSAGES[err.code] ?? "Sign-in failed. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="ops-login-page">
      <form className="ops-login-card" onSubmit={handleSubmit}>
        <div className="ops-sidebar-brand">Penta Operations</div>
        <p className="ops-login-subtitle">Sign in to review applications.</p>

        <label className="ops-login-label" htmlFor="ops-login-email">
          Email
        </label>
        <input
          id="ops-login-email"
          className="ops-login-input"
          type="email"
          autoComplete="username"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
        />

        <label className="ops-login-label" htmlFor="ops-login-password">
          Password
        </label>
        <input
          id="ops-login-password"
          className="ops-login-input"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          required
        />

        {error && <div className="ops-login-error">{error}</div>}

        <button className="ops-login-submit" type="submit" disabled={submitting}>
          {submitting ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
