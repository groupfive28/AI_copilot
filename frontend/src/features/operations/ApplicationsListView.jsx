import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { fetchApplications } from "./api.js";
import { APPLICATION_STATUS_CONFIG, STATUS_FILTER_OPTIONS } from "./constants.js";
import DataTable from "./DataTable.jsx";
import StatusBadge from "./StatusBadge.jsx";
import SummaryCards from "./SummaryCards.jsx";

function formatDate(isoString) {
  return new Date(isoString).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export default function ApplicationsListView() {
  const navigate = useNavigate();

  const [statusFilter, setStatusFilter] = useState("");
  const [sortBy, setSortBy] = useState("created_at");
  const [sortDir, setSortDir] = useState("desc");

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    fetchApplications({ status: statusFilter, sortBy, sortDir })
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
  }, [statusFilter, sortBy, sortDir]);

  function handleSort(key) {
    if (key === sortBy) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortBy(key);
      setSortDir("asc");
    }
  }

  const columns = [
    { key: "company_name", label: "Company", sortable: true },
    { key: "cac_registration_number", label: "CAC Reg. Number", sortable: true },
    {
      key: "status",
      label: "Status",
      sortable: true,
      render: (row) => {
        const cfg = APPLICATION_STATUS_CONFIG[row.status] ?? { label: row.status, role: "neutral" };
        return <StatusBadge role={cfg.role} label={cfg.label} />;
      },
    },
    {
      key: "created_at",
      label: "Submitted",
      sortable: true,
      render: (row) => <span className="ops-mono">{formatDate(row.created_at)}</span>,
    },
  ];

  return (
    <>
      <div className="ops-page-header">
        <h1>Applications</h1>
        <p>All corporate account applications received through onboarding.</p>
      </div>

      {data && <SummaryCards summary={data.summary} />}

      <div className="ops-filter-row">
        <select className="ops-select" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          {STATUS_FILTER_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {loading && <div className="ops-loading">Loading applications...</div>}
      {error && <div className="ops-error">{error}</div>}

      {!loading && !error && data && (
        <DataTable
          columns={columns}
          rows={data.items}
          sortBy={sortBy}
          sortDir={sortDir}
          onSort={handleSort}
          onRowClick={(row) => navigate(`/operations/applications/${row.id}`)}
          emptyMessage="No applications yet."
        />
      )}
    </>
  );
}
