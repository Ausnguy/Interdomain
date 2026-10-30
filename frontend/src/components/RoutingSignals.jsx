import Section from "./Section.jsx";
import StatusBadge from "./StatusBadge.jsx";
import { THRESHOLDS } from "../lib/signals.js";
import {
  formatNumber,
  formatPct,
  formatRegion,
} from "../lib/format.js";


const MAX_SIGNALS = 4;


export default function RoutingSignals({
  attentionSignals,
  feedIsLive,
}) {
  const shown = attentionSignals.slice(0, MAX_SIGNALS);
  const hidden = attentionSignals.length - shown.length;

  return (
    <Section
      id="signals"
      title="What needs attention"
      description={
        feedIsLive
          ? "Regions where an unusual share of routes are being withdrawn, most severe first."
          : "Regions where an unusual share of routes were withdrawn in the last stored hour, most severe first."
      }
    >
      {shown.length === 0 ? (
        <div className="all-clear" role="status">
          <p className="all-clear__title">
            No elevated regional signals
          </p>
          <p className="all-clear__body">
            Every region with at least {THRESHOLDS.minEvents} route changes
            in the last hour has a withdrawal share below{" "}
            {THRESHOLDS.elevated}%.
          </p>
        </div>
      ) : (
        <ul className="signals">
          {shown.map((signal) => (
            <li
              className="signal"
              key={signal.region}
              style={{ "--signal-color": `var(--sev-${signal.severity})` }}
            >
              <div className="signal__head">
                <h3 className="signal__region">
                  {formatRegion(signal.region)}
                </h3>
                <StatusBadge severity={signal.severity} size="sm" />
              </div>

              <p className="signal__rate">
                <span className="signal__rate-value">
                  {formatPct(signal.withdrawalRate)}
                </span>{" "}
                <span className="signal__rate-label">
                  withdrawal share
                </span>
              </p>

              <dl className="signal__stats">
                <div>
                  <dt>Route changes</dt>
                  <dd>{formatNumber(signal.total_events)}</dd>
                </div>
                <div>
                  <dt>Withdrawals</dt>
                  <dd>{formatNumber(signal.withdrawals)}</dd>
                </div>
                <div>
                  <dt>Collectors</dt>
                  <dd>{formatNumber(signal.collectors)}</dd>
                </div>
              </dl>
            </li>
          ))}
        </ul>
      )}

      {hidden > 0 && (
        <p className="section__footnote">
          <a href="#regions">
            {hidden} more {hidden === 1 ? "region" : "regions"} in
            Regional health
          </a>
        </p>
      )}
    </Section>
  );
}
