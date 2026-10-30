import { SEVERITY } from "../lib/signals.js";


// Severity is always text plus color, never color alone.
export default function StatusBadge({
  severity,
  label,
  size = "md",
}) {
  const info = SEVERITY[severity] || SEVERITY.normal;

  return (
    <span
      className={`status-badge status-badge--${size}`}
      style={{ "--badge-color": info.color }}
    >
      <span
        className="status-badge__dot"
        aria-hidden="true"
      />
      {label || info.label}
    </span>
  );
}
