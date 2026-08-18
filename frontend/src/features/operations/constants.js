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

// Order matters here - it's the left-to-right sequence of the pipeline
// stepper. Matches the stages backend/app/verification/service.py's
// run_post_submission_pipeline actually sets, in the order it sets them.
export const PIPELINE_STAGES = [
  { value: "extracting", label: "Extracting documents (OCR)" },
  { value: "verifying_faces", label: "Verifying faces" },
  { value: "verifying_signatures", label: "Verifying signatures" },
  { value: "checking_registries", label: "Checking registries" },
  { value: "done", label: "Done" },
];

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
  proof_of_address: "Utility Bill",
  govt_id_international_passport: "International Passport",
  govt_id_drivers_license: "Driver's License",
  govt_id_voters_card: "Voter's Card",
  govt_id_national_id_card: "National ID Card",
  board_resolution_form: "Board Resolution Form",
  cac_status_report: "CAC Status Report",
  // face_verification results have no real document to look up a category
  // for (see backend/app/operations/service.py's list_verification_failures) -
  // the backend synthesizes this exact value for them, since the director's
  // passport photo is the subject being verified.
  director_passport_photo: "Director's Passport Photo",
  // signature_verification results synthesize this the same way
  // face_verification synthesizes director_passport_photo above - see
  // backend/app/operations/service.py's list_verification_failures.
  director_signature_specimen: "Director's Signature Specimen",
};

export const CHECK_TYPE_LABELS = {
  registry_lookup: "Registry lookup",
  face_verification: "Face verification",
  signature_verification: "Signature verification",
};

export const STATUS_FILTER_OPTIONS = [
  { value: "", label: "All statuses" },
  ...Object.entries(APPLICATION_STATUS_CONFIG).map(([value, cfg]) => ({ value, label: cfg.label })),
];
