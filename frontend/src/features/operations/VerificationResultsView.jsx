import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { fetchVerificationResults } from "./api.js";
import { APPLICATION_STATUS_CONFIG, CHECK_STATUS_CONFIG, DOCUMENT_CATEGORY_LABELS } from "./constants.js";
import DiscrepancyDetails from "./DiscrepancyDetails.jsx";
import StatusBadge from "./StatusBadge.jsx";

function formatDate(isoString) {
  return new Date(isoString).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

const CHECK_TYPE_LABELS = {
  registry_lookup: "Registry lookup",
  face_verification: "Face verification",
};

export default function VerificationResultsView() {
  const [failedOnly, setFailedOnly] = useState(true);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    fetchVerificationResults({ failedOnly })
      .then((response) => {
        if (!cancelled) setData(response);
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
  }, [failedOnly]);

  return (
    <>
      <div className="ops-page-header">
        <h1>Verification results</h1>
        <p>Applications with document data checked against registry records or face verification.</p>
      </div>

      <div className="ops-filter-row">
        <div className="ops-toggle">
          <button className={failedOnly ? "active" : ""} onClick={() => setFailedOnly(true)}>
            Failed checks only
          </button>
          <button className={!failedOnly ? "active" : ""} onClick={() => setFailedOnly(false)}>
            All results
          </button>
        </div>
      </div>

      {loading && <div className="ops-loading">Loading verification results...</div>}
      {error && <div className="ops-error">{error}</div>}

      {!loading && !error && data && data.items.length === 0 && (
        <div className="ops-table-card">
          <div className="ops-table-empty">
            {failedOnly ? "No applications currently have failed checks." : "No verification results yet."}
          </div>
        </div>
      )}

      {!loading &&
        !error &&
        data &&
        data.items.map((group) => {
          const statusCfg = APPLICATION_STATUS_CONFIG[group.status] ?? { label: group.status, role: "neutral" };
          return (
            <div className="ops-failure-group" key={group.application_id}>
              <div className="ops-failure-group-header">
                <span className="ops-failure-group-title">
                  <Link to={`/operations/applications/${group.application_id}`}>{group.company_name}</Link>
                </span>
                <StatusBadge role={statusCfg.role} label={statusCfg.label} />
              </div>

              {group.failures.map((failure, idx) => {
                const stateCfg = CHECK_STATUS_CONFIG[failure.status] ?? { label: failure.status, role: "neutral" };
                return (
                  <div className="ops-failure-item" key={idx}>
                    <div className="ops-failure-item-header">
                      <span className="ops-failure-item-category">
                        {DOCUMENT_CATEGORY_LABELS[failure.document_category] ?? failure.document_category ?? "Unknown document"}
                      </span>
                      <StatusBadge role={stateCfg.role} label={stateCfg.label} />
                      <span className="ops-mono">{CHECK_TYPE_LABELS[failure.check_type] ?? failure.check_type}</span>
                      <span className="ops-mono">{formatDate(failure.created_at)}</span>
                    </div>
                    <DiscrepancyDetails registryTable={failure.registry_table} details={failure.discrepancy_details} />
                  </div>
                );
              })}
            </div>
          );
        })}
    </>
  );
}
