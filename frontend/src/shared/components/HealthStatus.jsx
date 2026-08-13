import { useEffect, useState } from "react";

import { apiRequest } from "../api/client.js";

/**
 * Pings the backend's /health endpoint on mount to prove the frontend and
 * backend are wired together. Not tied to any of the four business layers.
 */
export default function HealthStatus() {
  const [state, setState] = useState("checking");

  useEffect(() => {
    let cancelled = false;

    apiRequest("/health")
      .then((data) => {
        if (!cancelled) setState(data.status === "ok" ? "ok" : "error");
      })
      .catch(() => {
        if (!cancelled) setState("error");
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const label =
    state === "checking" ? "Checking backend..." : state === "ok" ? "Backend connected" : "Backend unreachable";

  return (
    <div className="status-bar">
      <span className={`status-dot ${state}`} />
      {label}
    </div>
  );
}
