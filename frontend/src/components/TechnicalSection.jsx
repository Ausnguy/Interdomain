import {
  Bar,
  BarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import RoutingEventsTable from "./RoutingEventsTable.jsx";
import StatusBadge from "./StatusBadge.jsx";
import { POLL_INTERVAL_MS } from "../hooks/useInterdomainData.js";
import {
  collectorId,
  formatAsn,
  formatNumber,
  formatPct,
  formatRegion,
  formatTime,
} from "../lib/format.js";


function AsnTooltip({ active, payload }) {
  if (!active || !payload?.length) {
    return null;
  }

  const point = payload[0].payload;

  return (
    <div className="chart-tooltip">
      <p className="chart-tooltip__title mono">{formatAsn(point.peer_asn)}</p>
      <p>{formatNumber(point.update_count)} route changes in the last hour</p>
    </div>
  );
}


function Panel({ id, title, description, children }) {
  const headingId = `${id}-heading`;

  return (
    <section
      id={id}
      className="panel"
      aria-labelledby={headingId}
    >
      <h3 id={headingId}>{title}</h3>
      {description && <p className="panel__description">{description}</p>}
      {children}
    </section>
  );
}


export default function TechnicalSection({
  asns,
  withdrawals,
  routes,
  collectorRows,
}) {
  return (
    <section
      id="technical"
      className="technical"
      aria-labelledby="technical-heading"
    >
      <header className="technical__header">
        <h2 id="technical-heading">Technical investigation</h2>
        <p className="section__description">
          The raw BGP data behind the signals above: which peer networks are
          most active, which prefixes were withdrawn, what each collector is
          seeing, and individual route updates.
        </p>
      </header>

      <div className="technical__grid">
        <Panel
          id="asns"
          title="Most active peer networks"
          description="Peer ASNs sending the most updates to RIPE collectors in the last hour."
        >
          <div
            className="asn-chart"
            role="img"
            aria-label={asns
              .map((asn) => `${formatAsn(asn.peer_asn)}: ${formatNumber(asn.update_count)}`)
              .join(", ")}
          >
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={asns}
                layout="vertical"
                margin={{ top: 0, right: 16, bottom: 0, left: 0 }}
              >
                <XAxis type="number" hide />
                <YAxis
                  type="category"
                  dataKey="peer_asn"
                  width={84}
                  tickFormatter={formatAsn}
                  tickLine={false}
                  axisLine={false}
                  tick={{
                    fill: "var(--ink-2)",
                    fontSize: 12,
                    fontFamily: "var(--font-mono)",
                  }}
                />
                <Tooltip
                  content={<AsnTooltip />}
                  cursor={{ fill: "var(--hover)" }}
                />
                <Bar
                  dataKey="update_count"
                  name="Route changes"
                  fill="var(--chart-primary)"
                  radius={[0, 3, 3, 0]}
                  barSize={14}
                  isAnimationActive={false}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Panel>

        <Panel
          id="withdrawals"
          title="Recent withdrawals"
          description="The latest prefixes removed from routing, newest first."
        >
          <div className="table-wrap">
            <table className="data-table compact-table">
              <caption className="visually-hidden">
                Most recent withdrawn prefixes
              </caption>
              <thead>
                <tr>
                  <th scope="col">Prefix</th>
                  <th scope="col">Peer</th>
                  <th scope="col" className="num">Withdrawn</th>
                </tr>
              </thead>
              <tbody>
                {withdrawals.map((item, index) => (
                  <tr key={`${item.prefix}-${index}`}>
                    <td className="mono">{item.prefix}</td>
                    <td className="mono">{formatAsn(item.peer_asn)}</td>
                    <td className="num muted">{formatTime(item.observed_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>

            {withdrawals.length === 0 && (
              <p className="empty">No withdrawals stored yet.</p>
            )}
          </div>
        </Panel>
      </div>

      <Panel
        id="collectors"
        title="Collectors"
        description="What each RIPE RIS collector observed in the last hour. This is the same data as the map."
      >
        <div className="table-wrap">
          <table className="data-table">
            <caption className="visually-hidden">
              Route collector activity, last hour, most severe first
            </caption>
            <thead>
              <tr>
                <th scope="col">Collector</th>
                <th scope="col">Location</th>
                <th scope="col">Region</th>
                <th scope="col">Status</th>
                <th scope="col" className="num">Route changes</th>
                <th scope="col" className="num">Announcements</th>
                <th scope="col" className="num">Withdrawals</th>
                <th scope="col" className="num">Withdrawal share</th>
              </tr>
            </thead>
            <tbody>
              {collectorRows.map((collector) => (
                <tr key={collector.collector}>
                  <th scope="row" className="mono">
                    {collectorId(collector.collector).toUpperCase()}
                  </th>
                  <td>
                    {collector.city
                      ? `${collector.city}, ${collector.country}`
                      : "Unknown"}
                  </td>
                  <td>{formatRegion(collector.collector_region)}</td>
                  <td>
                    <StatusBadge severity={collector.severity} size="sm" />
                  </td>
                  <td className="num">{formatNumber(collector.total_events)}</td>
                  <td className="num">{formatNumber(collector.announcements)}</td>
                  <td className="num">{formatNumber(collector.withdrawals)}</td>
                  <td className="num">{formatPct(collector.withdrawalRate)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <Panel
        id="events"
        title="Recent routing events"
        description={`The ${routes.length} newest BGP updates. Refreshes every ${POLL_INTERVAL_MS / 1000} seconds.`}
      >
        <RoutingEventsTable routes={routes} />
      </Panel>
    </section>
  );
}
