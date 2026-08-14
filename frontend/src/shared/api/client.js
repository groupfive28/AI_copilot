const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

/**
 * Thin fetch wrapper shared by all features. Throws on non-2xx responses so
 * callers can rely on try/catch instead of checking `response.ok` everywhere.
 */
export async function apiRequest(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, options);

  if (!response.ok) {
    const detail = await response.text().catch(() => "");
    throw new Error(`Request to ${path} failed (${response.status}): ${detail}`);
  }

  return response.json();
}

export { API_BASE_URL };
