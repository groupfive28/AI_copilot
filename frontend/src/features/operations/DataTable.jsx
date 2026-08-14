/**
 * Generic sortable data table. `columns` is [{ key, label, sortable, render(row) }].
 * Sorting is server-driven: sortBy/sortDir reflect current state, onSort(key) requests a change.
 */
export default function DataTable({ columns, rows, sortBy, sortDir, onSort, onRowClick, emptyMessage }) {
  if (rows.length === 0) {
    return (
      <div className="ops-table-card">
        <div className="ops-table-empty">{emptyMessage || "No results."}</div>
      </div>
    );
  }

  return (
    <div className="ops-table-card">
      <table className="ops-table">
        <thead>
          <tr>
            {columns.map((col) => (
              <th
                key={col.key}
                className={col.sortable ? "sortable" : ""}
                onClick={col.sortable ? () => onSort(col.key) : undefined}
              >
                {col.label}
                {col.sortable && sortBy === col.key && (
                  <span className="ops-sort-indicator">{sortDir === "asc" ? "↑" : "↓"}</span>
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id} className={onRowClick ? "clickable" : ""} onClick={onRowClick ? () => onRowClick(row) : undefined}>
              {columns.map((col) => (
                <td key={col.key}>{col.render ? col.render(row) : row[col.key]}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
