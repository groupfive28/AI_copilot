import { apiRequest } from "../../shared/api/client.js";

export function fetchApplications({ status, sortBy, sortDir }) {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  if (sortBy) params.set("sort_by", sortBy);
  if (sortDir) params.set("sort_dir", sortDir);
  return apiRequest(`/api/v1/operations/applications?${params.toString()}`);
}

export function fetchApplicationDetail(applicationId) {
  return apiRequest(`/api/v1/operations/applications/${applicationId}`);
}

export function fetchVerificationResults({ failedOnly }) {
  const params = new URLSearchParams({ failed_only: String(failedOnly) });
  return apiRequest(`/api/v1/operations/verification-results?${params.toString()}`);
}
