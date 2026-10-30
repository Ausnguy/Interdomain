// Severity is a transparent heuristic, not anomaly detection: the share of
// route changes that are withdrawals over the last hour. There is no
// historical baseline yet, so the UI must describe it in these terms.
export const THRESHOLDS = {
  minEvents: 100,
  elevated: 5,
  high: 10,
  critical: 20,
};


// Colors resolve to CSS custom properties so light and dark themes share
// one source of truth. SVG presentation attributes (Leaflet, Recharts)
// accept var() in all current browsers.
export const SEVERITY = {
  normal: {
    label: "Normal",
    color: "var(--sev-normal)",
  },
  elevated: {
    label: "Elevated",
    color: "var(--sev-elevated)",
  },
  high: {
    label: "High",
    color: "var(--sev-high)",
  },
  critical: {
    label: "Critical",
    color: "var(--sev-critical)",
  },
  stale: {
    label: "Stale",
    color: "var(--sev-unavailable)",
  },
  offline: {
    label: "Offline",
    color: "var(--sev-unavailable)",
  },
};


export const SIGNAL_LEVELS = [
  "normal",
  "elevated",
  "high",
  "critical",
];


export function deriveSignal(item) {
  const total = Number(item?.total_events || 0);
  const withdrawals = Number(item?.withdrawals || 0);

  const withdrawalRate =
    total > 0
      ? (withdrawals / total) * 100
      : 0;

  let severity = "normal";

  if (total >= THRESHOLDS.minEvents) {
    if (withdrawalRate >= THRESHOLDS.critical) {
      severity = "critical";
    } else if (withdrawalRate >= THRESHOLDS.high) {
      severity = "high";
    } else if (withdrawalRate >= THRESHOLDS.elevated) {
      severity = "elevated";
    }
  }

  return {
    severity,
    withdrawalRate,
  };
}


export function severityRank(severity) {
  return {
    normal: 0,
    elevated: 1,
    high: 2,
    critical: 3,
  }[severity] ?? 0;
}


// Highest severity first, then busiest first.
export function compareSignals(a, b) {
  return (
    severityRank(b.severity) -
      severityRank(a.severity) ||
    Number(b.total_events) -
      Number(a.total_events)
  );
}
