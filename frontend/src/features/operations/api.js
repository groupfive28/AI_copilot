import { apiRequest } from "../../shared/api/client.js";
import { getIdToken } from "../../shared/firebase/client.js";

async function authedRequest(path, options = {}) {
  const token = await getIdToken();
  const headers = { ...(options.headers ?? {}), ...(token ? { Authorization: `Bearer ${token}` } : {}) };
  return apiRequest(path, { ...options, headers });
}

export function fetchApplications({ status, sortBy, sortDir }) {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  if (sortBy) params.set("sort_by", sortBy);
  if (sortDir) params.set("sort_dir", sortDir);
  return authedRequest(`/api/v1/operations/applications?${params.toString()}`);
}

export function fetchApplicationDetail(applicationId) {
  return authedRequest(`/api/v1/operations/applications/${applicationId}`);
}

export function fetchVerificationResults({ failedOnly }) {
  const params = new URLSearchParams({ failed_only: String(failedOnly) });
  return authedRequest(`/api/v1/operations/verification-results?${params.toString()}`);
}

export function submitApplicationDecision(applicationId, decision, note) {
  return authedRequest(`/api/v1/operations/applications/${applicationId}/decision`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ decision, note: note?.trim() || null }),
  });
}

export function reuploadDocument(applicationId, documentCategory, file, note) {
  const formData = new FormData();
  formData.append("file", file);
  if (note?.trim()) formData.append("note", note.trim());
  // No Content-Type header here on purpose - the browser sets
  // multipart/form-data with the correct boundary itself; setting it
  // manually breaks the boundary and the backend fails to parse the body.
  return authedRequest(`/api/v1/operations/applications/${applicationId}/documents/${documentCategory}/reupload`, {
    method: "POST",
    body: formData,
  });
}
