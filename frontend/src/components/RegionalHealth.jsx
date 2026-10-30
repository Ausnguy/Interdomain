import Section from "./Section.jsx";
import StatusBadge from "./StatusBadge.jsx";
import {
  formatNumber,
  formatPct,
  formatRegion,
} from "../lib/format.js";


export default function RegionalHealth({ regionSignals }) {
  const maxEvents = Math.max(
    ...regionSignals.map((region) => Number(region.total_events)),
    1
  );

  return (
    <Section
      id="regions"
      title="Regional health"
      description="Every region observed in the last hour. Regions are based on where RIPE collectors are located; Global covers collectors that peer with networks worldwide."
    >
      <div className="table-wrap">
        <table className="data-table region-table">
          <caption className="visually-hidden">
            Routing health by region, last hour, most severe first
          </caption>

          <thead>
            <tr>
              <th scope="col">Region</th>
              <th scope="col">Status</th>
              <th scope="col" className="num">Route changes</th>
              <th scope="col" className="num">Withdrawal share</th>
              <th scope="col" className="region-table__mix-head">
                Volume and mix
                <span className="region-table__mix-key">
                  <i className="mix-key mix-key--ann" /> announced
                  <i className="mix-key mix-key--wd" /> withdrawn
                </span>
              </th>
            </tr>
          </thead>

          <tbody>
            {regionSignals.map((region) => {
              const total = Number(region.total_events);
              const withdrawn = Number(region.withdrawals);
              const announced = Number(region.announcements);

              return (
                <tr key={region.region}>
                  <th scope="row">{formatRegion(region.region)}</th>
                  <td>
                    <StatusBadge severity={region.severity} size="sm" />
                  </td>
                  <td className="num">{formatNumber(total)}</td>
                  <td className="num">{formatPct(region.withdrawalRate)}</td>
                  <td>
                    <div
                      className="mix-bar"
                      role="img"
                      aria-label={`${formatNumber(announced)} announcements, ${formatNumber(withdrawn)} withdrawals`}
                      style={{ width: `${Math.max((total / maxEvents) * 100, 2)}%` }}
                    >
                      <span
                        className="mix-bar__ann"
                        style={{ flexGrow: announced }}
                      />
                      <span
                        className="mix-bar__wd"
                        style={{ flexGrow: withdrawn }}
                      />
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Section>
  );
}
