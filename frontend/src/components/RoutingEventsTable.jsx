import {
  collectorId,
  formatAsn,
  formatAsPath,
  formatRegion,
  formatTime,
} from "../lib/format.js";


const EVENT_LABELS = {
  announcement: "Announced",
  withdrawal: "Withdrawn",
};


export default function RoutingEventsTable({ routes }) {
  return (
    <div className="table-wrap">
      <table className="data-table events-table">
        <caption className="visually-hidden">
          Most recent BGP updates, newest first
        </caption>

        <thead>
          <tr>
            <th scope="col">Event</th>
            <th scope="col">Prefix</th>
            <th scope="col">Peer</th>
            <th scope="col">AS path</th>
            <th scope="col">Region</th>
            <th scope="col">Collector</th>
            <th scope="col" className="num">Observed</th>
          </tr>
        </thead>

        <tbody>
          {routes.map((route, index) => {
            const path = formatAsPath(route.as_path);

            return (
              <tr key={`${route.prefix}-${route.observed_at}-${index}`}>
                <td>
                  <span className={`event-tag event-tag--${route.event_type}`}>
                    {EVENT_LABELS[route.event_type] || route.event_type}
                  </span>
                </td>
                <td className="mono">{route.prefix}</td>
                <td className="mono">{formatAsn(route.peer_asn)}</td>
                <td className="mono events-table__path" title={path}>
                  {path}
                </td>
                <td>{formatRegion(route.collector_region)}</td>
                <td className="mono">
                  {route.collector
                    ? collectorId(route.collector).toUpperCase()
                    : "—"}
                </td>
                <td className="num muted">{formatTime(route.observed_at)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {routes.length === 0 && (
        <p className="empty">No routing events stored yet.</p>
      )}
    </div>
  );
}
