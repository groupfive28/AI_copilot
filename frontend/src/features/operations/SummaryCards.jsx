export default function SummaryCards({ summary }) {
  const tiles = [
    { label: "Total applications", value: summary.total },
    { label: "Pending review", value: summary.pending_review },
    { label: "Verification failures", value: summary.verification_failures, critical: summary.verification_failures > 0 },
  ];

  return (
    <div className="ops-stat-row">
      {tiles.map((tile) => (
        <div className="ops-stat-tile" key={tile.label}>
          <div className="ops-stat-tile-label">{tile.label}</div>
          <div className={`ops-stat-tile-value ${tile.critical ? "role-critical" : ""}`}>{tile.value}</div>
        </div>
      ))}
    </div>
  );
}
