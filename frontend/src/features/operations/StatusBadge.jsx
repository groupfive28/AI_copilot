// Status color is never the only signal - every badge pairs the color with a
// text label (per the dataviz skill's status-palette rule: reserved colors
// ship with an icon/dot + label, never color alone).
export default function StatusBadge({ role, label }) {
  return (
    <span className={`ops-badge role-${role}`}>
      <span className="ops-badge-dot" />
      {label}
    </span>
  );
}
