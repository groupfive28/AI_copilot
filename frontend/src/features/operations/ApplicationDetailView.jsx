import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { fetchApplicationDetail, reuploadDocument, submitApplicationDecision } from "./api.js";
import {
  APPLICATION_STATUS_CONFIG,
  CHECK_STATUS_CONFIG,
  CHECK_TYPE_LABELS,
  DOCUMENT_CATEGORY_LABELS,
  DOCUMENT_STATE_CONFIG,
} from "./constants.js";
import DiscrepancyDetails from "./DiscrepancyDetails.jsx";
import PipelineStepper from "./PipelineStepper.jsx";
import StatusBadge from "./StatusBadge.jsx";

// Only relevant while the background pipeline could still be running - see
// the polling effect below.
const POLL_INTERVAL_MS = 4000;
const NON_TERMINAL_STATUSES = new Set(["received", "processing"]);

function formatDate(isoString) {
  if (!isoString) return "—";
  return new Date(isoString).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

const DECISIONS = [
  { value: "approved", label: "Approve" },
  { value: "escalated", label: "Escalate" },
  { value: "rejected", label: "Reject" },
];

function DecisionPanel({ applicationId, currentStatus, onDecided }) {
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(null);
  const [error, setError] = useState(null);

  async function handleDecide(decision) {
    setSubmitting(decision);
    setError(null);
    try {
      const updated = await submitApplicationDecision(applicationId, decision, note);
      setNote("");
      onDecided(updated);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(null);
    }
  }

  return (
    <div className="ops-card">
      <h2>Decision</h2>
      <textarea
        className="ops-decision-note"
        placeholder="Optional note (visible in this application's activity log)"
        value={note}
        onChange={(event) => setNote(event.target.value)}
        rows={2}
      />
      <div className="ops-decision-actions">
        {DECISIONS.map(({ value, label }) => (
          <button
            key={value}
            type="button"
            className={`ops-decision-button role-${value}`}
            disabled={submitting !== null || currentStatus === value}
            onClick={() => handleDecide(value)}
          >
            {submitting === value ? "Saving…" : label}
          </button>
        ))}
      </div>
      {error && <div className="ops-login-error">{error}</div>}
    </div>
  );
}

// Admin-initiated only, on purpose - not a customer-facing self-service
// re-upload. The reviewer has already confirmed the document is genuinely
// wrong and obtained a correction from the applicant out of band (email,
// phone, in person) before using this.
function DocumentReuploadForm({ applicationId, documentCategory, onReuploaded }) {
  const [file, setFile] = useState(null);
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [fileInputKey, setFileInputKey] = useState(0);

  async function handleSubmit(event) {
    event.preventDefault();
    if (!file) {
      setError("Choose a replacement file first.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await reuploadDocument(applicationId, documentCategory, file, note);
      setFile(null);
      setNote("");
      setFileInputKey((key) => key + 1);
      onReuploaded();
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="ops-reupload-form" onSubmit={handleSubmit}>
      <input
        key={fileInputKey}
        type="file"
        accept=".jpg,.jpeg,.png,.webp,.pdf"
        onChange={(event) => setFile(event.target.files?.[0] ?? null)}
      />
      <input
        type="text"
        className="ops-reupload-note"
        placeholder="Optional note (e.g. why the original was wrong)"
        value={note}
        onChange={(event) => setNote(event.target.value)}
      />
      <button type="submit" className="ops-reupload-button" disabled={submitting}>
        {submitting ? "Uploading…" : "Upload replacement"}
      </button>
      {error && <div className="ops-login-error">{error}</div>}
    </form>
  );
}

function ActivityLog({ entries }) {
  if (!entries.length) {
    return <p className="ops-registry-note">No activity recorded yet.</p>;
  }
  return (
    <div className="ops-document-list">
      {entries.map((entry) => (
        <div key={entry.id} className="ops-document-row ops-activity-row">
          <div>
            <div className="ops-document-name">
              {entry.event_type === "status_changed"
                ? `${entry.event_details?.from_status ?? "?"} → ${entry.event_details?.to_status ?? "?"}`
                : entry.event_type}
            </div>
            {entry.event_details?.note && <div className="ops-field-label">"{entry.event_details.note}"</div>}
            {entry.event_details?.changed_by && (
              <div className="ops-field-label">by {entry.event_details.changed_by}</div>
            )}
          </div>
          <span className="ops-field-label">{formatDate(entry.created_at)}</span>
        </div>
      ))}
    </div>
  );
}

// The "document" a face/signature check is actually about (see
// backend/app/operations/service.py's get_application_detail - these
// results have no real document_id to join a category from, so there's
// nothing to look up from the application's `documents` list the way
// registry_lookup results work).
const BIOMETRIC_DOCUMENT_LABEL = {
  face_verification: DOCUMENT_CATEGORY_LABELS.director_passport_photo,
  signature_verification: DOCUMENT_CATEGORY_LABELS.director_signature_specimen,
};

function BiometricChecks({ checks }) {
  if (!checks.length) {
    return <p className="ops-registry-note">No face or signature checks recorded yet.</p>;
  }
  return (
    <div className="ops-document-list">
      {checks.map((check, idx) => {
        const cfg = CHECK_STATUS_CONFIG[check.status] ?? { label: check.status, role: "neutral" };
        const needsAttention = check.status === "mismatch" || check.status === "error";
        const directorLabel =
          check.director_name ?? (check.director_index != null ? `Director ${check.director_index + 1}` : null);
        return (
          <div key={idx}>
            <div className="ops-document-row">
              <span className="ops-document-name">
                {BIOMETRIC_DOCUMENT_LABEL[check.check_type] ?? CHECK_TYPE_LABELS[check.check_type] ?? check.check_type}
                {directorLabel && ` — ${directorLabel}`}
              </span>
              <StatusBadge role={cfg.role} label={cfg.label} />
            </div>
            {needsAttention && <DiscrepancyDetails details={check.discrepancy_details} />}
          </div>
        );
      })}
    </div>
  );
}

export default function ApplicationDetailView() {
  const { applicationId } = useParams();
  const [application, setApplication] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    fetchApplicationDetail(applicationId)
      .then((data) => {
        if (!cancelled) setApplication(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [applicationId]);

  // Poll while the background pipeline could still be running, so status/
  // stage changes show up without a manual page refresh. Restarts whenever
  // status changes and stops entirely once the application reaches a
  // terminal status (approved/rejected/escalated).
  useEffect(() => {
    if (!application || !NON_TERMINAL_STATUSES.has(application.status)) return undefined;

    let cancelled = false;
    const intervalId = setInterval(() => {
      fetchApplicationDetail(applicationId)
        .then((data) => {
          if (!cancelled) setApplication(data);
        })
        .catch(() => {});
    }, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      clearInterval(intervalId);
    };
  }, [applicationId, application?.status]);

  if (loading) return <div className="ops-loading">Loading application...</div>;
  if (error) return <div className="ops-error">{error}</div>;
  if (!application) return null;

  const statusCfg = APPLICATION_STATUS_CONFIG[application.status] ?? { label: application.status, role: "neutral" };

  function handleDecided(updated) {
    setApplication((prev) => ({ ...prev, status: updated.status, updated_at: updated.updated_at }));
    // Re-fetch to pick up the new audit_log entry rather than reconstructing it client-side.
    fetchApplicationDetail(applicationId).then(setApplication).catch(() => {});
  }

  function handleReuploaded() {
    // Status resets to "processing" server-side, which re-arms the polling
    // effect above (its dependency is application?.status) - no extra
    // polling wiring needed here, just picking up that new status.
    fetchApplicationDetail(applicationId).then(setApplication).catch(() => {});
  }

  return (
    <>
      <Link to="/operations" className="ops-back-link">
        ← Back to applications
      </Link>

      <div className="ops-page-header">
        <h1>{application.company_name}</h1>
        <p>
          <StatusBadge role={statusCfg.role} label={statusCfg.label} /> &nbsp;Submitted {formatDate(application.created_at)}
        </p>
        <PipelineStepper stage={application.pipeline_stage} />
      </div>

      <div className="ops-detail-grid">
        <div className="ops-card">
          <h2>CAC certificate details</h2>
          <div className="ops-field-row">
            <span className="ops-field-label">RC / Registration number</span>
            <span className="ops-field-value">{application.cac_registration_number}</span>
          </div>
          <div className="ops-field-row">
            <span className="ops-field-label">Business type</span>
            <span className="ops-field-value">{application.business_type ?? "—"}</span>
          </div>
          <div className="ops-field-row">
            <span className="ops-field-label">Date of registration</span>
            <span className="ops-field-value">{application.date_of_registration ?? "—"}</span>
          </div>
          <div className="ops-field-row">
            <span className="ops-field-label">TIN</span>
            <span className="ops-field-value">{application.tin}</span>
          </div>
          <div className="ops-field-row">
            <span className="ops-field-label">Company address</span>
            <span className="ops-field-value">{application.company_address ?? "—"}</span>
          </div>
        </div>

        <div className="ops-card">
          <h2>Signatory information</h2>
          <div className="ops-field-row">
            <span className="ops-field-label">Full name</span>
            <span className="ops-field-value">{application.signatory_full_name ?? "—"}</span>
          </div>
          <div className="ops-field-row">
            <span className="ops-field-label">Email</span>
            <span className="ops-field-value">{application.signatory_email ?? "—"}</span>
          </div>
          <div className="ops-field-row">
            <span className="ops-field-label">Phone</span>
            <span className="ops-field-value">{application.signatory_phone_number ?? "—"}</span>
          </div>
          <div className="ops-field-row">
            <span className="ops-field-label">Designation</span>
            <span className="ops-field-value">{application.signatory_designation ?? "—"}</span>
          </div>
        </div>
      </div>

      <div className="ops-card">
        <h2>Submitted documents</h2>
        <div className="ops-document-list">
          {application.documents.map((doc) => {
            const cfg = DOCUMENT_STATE_CONFIG[doc.state] ?? { label: doc.state, role: "neutral" };
            const needsAttention = doc.state === "mismatch" || doc.state === "not_found" || doc.state === "error";
            return (
              <div key={doc.document_id}>
                <div className="ops-document-row">
                  <span className="ops-document-name">
                    {DOCUMENT_CATEGORY_LABELS[doc.document_category] ?? doc.document_category}
                  </span>
                  <StatusBadge role={cfg.role} label={cfg.label} />
                </div>
                {needsAttention && (
                  <>
                    <DiscrepancyDetails registryTable={doc.registry_table} details={doc.discrepancy_details} />
                    <DocumentReuploadForm
                      applicationId={application.id}
                      documentCategory={doc.document_category}
                      onReuploaded={handleReuploaded}
                    />
                  </>
                )}
              </div>
            );
          })}
        </div>
      </div>

      <div className="ops-card">
        <h2>Face &amp; signature checks</h2>
        <BiometricChecks checks={application.biometric_checks ?? []} />
      </div>

      <div className="ops-detail-grid">
        <DecisionPanel applicationId={application.id} currentStatus={application.status} onDecided={handleDecided} />

        <div className="ops-card">
          <h2>Activity</h2>
          <ActivityLog entries={application.audit_log ?? []} />
        </div>
      </div>
    </>
  );
}
