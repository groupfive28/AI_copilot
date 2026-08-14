// Status-palette roles (good/warning/serious/critical) are reserved for
// severity signaling and never reused for anything else. "received" and
// "processing" are neutral pipeline states, not severities, so they get a
// separate neutral/info treatment instead of borrowing a severity color.
export const APPLICATION_STATUS_CONFIG = {
  received: { label: "Received", role: "neutral" },
  processing: { label: "Processing", role: "info" },
  escalated: { label: "Escalated", role: "warning" },
  approved: { label: "Approved", role: "good" },
  rejected: { label: "Rejected", role: "critical" },
};

export const DOCUMENT_STATE_CONFIG = {
  pending: { label: "Pending", role: "neutral" },
  verified: { label: "Verified", role: "good" },
  mismatch: { label: "Mismatch", role: "serious" },
  not_found: { label: "Not found", role: "warning" },
  error: { label: "Error", role: "critical" },
};

// verification_results.status as returned raw by the verification-results
// endpoint - "match" rather than "verified" (see DOCUMENT_STATE_CONFIG,
// which is for the application-detail view's derived per-document state).
export const CHECK_STATUS_CONFIG = {
  match: { label: "Match", role: "good" },
  mismatch: { label: "Mismatch", role: "serious" },
  not_found: { label: "Not found", role: "warning" },
  error: { label: "Error", role: "critical" },
};

export const DOCUMENT_CATEGORY_LABELS = {
  cac_certificate: "CAC Certificate",
  tin: "TIN Certificate",
  nin: "NIN",
  bvn: "BVN",
  voters_card: "Voter's Card",
  passport_or_drivers_license: "Passport / Driver's License",
  proof_of_address: "Proof of Address",
};

export const STATUS_FILTER_OPTIONS = [
  { value: "", label: "All statuses" },
  ...Object.entries(APPLICATION_STATUS_CONFIG).map(([value, cfg]) => ({ value, label: cfg.label })),
];
