// discrepancy_details is an arbitrary JSONB blob - there's no fixed shape
// yet since the OCR/verification pipeline that produces it isn't built.
// Rendered as a generic key/value table rather than assuming field names,
// with a JSON fallback for nested values, so it still reads clearly once
// the real shape lands.
export default function DiscrepancyDetails({ registryTable, details }) {
  const entries = details ? Object.entries(details) : [];

  if (entries.length === 0) {
    return <p className="ops-discrepancy-raw">No discrepancy details recorded.</p>;
  }

  return (
    <div>
      {registryTable && (
        <p className="ops-registry-note">
          Checked against <strong>{registryTable}</strong>
        </p>
      )}
      <table className="ops-discrepancy-table">
        <thead>
          <tr>
            <th>Field</th>
            <th>Detail</th>
          </tr>
        </thead>
        <tbody>
          {entries.map(([key, value]) => (
            <tr key={key}>
              <td>{key}</td>
              <td>{typeof value === "object" && value !== null ? JSON.stringify(value) : String(value)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
