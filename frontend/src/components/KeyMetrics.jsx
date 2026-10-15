import {
  formatNumber,
  formatPct,
} from "../lib/format.js";


function Metric({ label, value, detail }) {
  return (
    <div className="metric">
      <dt className="metric__label">{label}</dt>
      <dd className="metric__value">{formatNumber(value)}</dd>
      <dd className="metric__detail">{detail}</dd>
    </div>
  );
}


export default function KeyMetrics({
  summary,
  regionCount,
  collectorCount,
}) {
  const total = Number(summary.total_events || 0);
  const removed = Number(summary.withdrawals || 0);
  const share = total > 0 ? (removed / total) * 100 : 0;

  return (
    <section
      className="metrics"
      aria-label="Key health metrics, last hour"
    >
      <dl className="metrics__list">
        <Metric
          label="Route changes"
          value={total}
          detail={`BGP updates in the last hour, across ${formatNumber(summary.unique_prefixes)} prefixes`}
        />

        <Metric
          label="Routes removed"
          value={removed}
          detail={`BGP withdrawals, ${formatPct(share)} of all changes`}
        />

        <Metric
          label="Regions observed"
          value={regionCount}
          detail="Grouped by collector location"
        />

        <Metric
          label="Active collectors"
          value={collectorCount}
          detail={`RIPE RIS route collectors, hearing ${formatNumber(summary.unique_peer_asns)} peer networks`}
        />
      </dl>
    </section>
  );
}
