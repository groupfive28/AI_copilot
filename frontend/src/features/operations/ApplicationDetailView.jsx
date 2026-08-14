import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { fetchApplicationDetail } from "./api.js";
import { APPLICATION_STATUS_CONFIG, DOCUMENT_CATEGORY_LABELS, DOCUMENT_STATE_CONFIG } from "./constants.js";
import DiscrepancyDetails from "./DiscrepancyDetails.jsx";
import StatusBadge from "./StatusBadge.jsx";

function formatDate(isoString) {
  if (!isoString) return "—";
  return new Date(isoString).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
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

  if (loading) return <div className="ops-loading">Loading application...</div>;
  if (error) return <div className="ops-error">{error}</div>;
  if (!application) return null;

  const statusCfg = APPLICATION_STATUS_CONFIG[application.status] ?? { label: application.status, role: "neutral" };

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
            <span className="ops-field-value">{application.business_type}</span>
          </div>
          <div className="ops-field-row">
            <span className="ops-field-label">Date of registration</span>
            <span className="ops-field-value">{application.date_of_registration ?? "—"}</span>
          </div>
          <div className="ops-field-row">
            <span className="ops-field-label">TIN</span>
            <span className="ops-field-value">{application.tin}</span>
          </div>
        </div>

        <div className="ops-card">
          <h2>Signatory information</h2>
          <div className="ops-field-row">
            <span className="ops-field-label">Full name</span>
            <span className="ops-field-value">{application.signatory_full_name}</span>
          </div>
          <div className="ops-field-row">
            <span className="ops-field-label">Email</span>
            <span className="ops-field-value">{application.signatory_email}</span>
          </div>
          <div className="ops-field-row">
            <span className="ops-field-label">Phone</span>
            <span className="ops-field-value">{application.signatory_phone_number}</span>
          </div>
          <div className="ops-field-row">
            <span className="ops-field-label">Designation</span>
            <span className="ops-field-value">{application.signatory_designation}</span>
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
                  <DiscrepancyDetails registryTable={doc.registry_table} details={doc.discrepancy_details} />
                )}
              </div>
            );
          })}
        </div>
      </div>
    </>
  );
}
