import StatusBadge from "./StatusBadge.jsx";
import { SEVERITY, THRESHOLDS } from "../lib/signals.js";
import {
  formatAge,
  formatRegion,
  formatTime,
  joinNames,
} from "../lib/format.js";


function describe({
  globalStatus,
  attentionSignals,
  regionCount,
  ageSeconds,
}) {
  const names = attentionSignals.map((signal) =>
    formatRegion(signal.region)
  );

  const storedNote =
    names.length > 0
      ? ` In the last stored hour, ${joinNames(names)} showed an elevated share of withdrawn routes.`
      : "";

  if (globalStatus === "offline") {
    return {
      headline: "No live routing data",
      body: `The newest event arrived ${formatAge(ageSeconds)}. Everything below comes from the last hour of stored events, not current conditions.${storedNote}`,
    };
  }

  if (globalStatus === "stale") {
    return {
      headline: "Live routing data is delayed",
      body: `The newest event is ${formatAge(ageSeconds).replace(" ago", "")} old. Figures may not reflect what is happening right now.${storedNote}`,
    };
  }

  if (globalStatus === "normal") {
    return {
      headline: `Routing looks normal across ${regionCount} ${regionCount === 1 ? "region" : "regions"}`,
      body: `No region has an unusual share of routes being withdrawn in the last hour.`,
    };
  }

  const worst = SEVERITY[globalStatus].label;

  const where =
    names.length > 3
      ? `${names.length} regions`
      : joinNames(names);

  return {
    headline: `${worst} route withdrawals in ${where}`,
    body: `At least ${THRESHOLDS.elevated}% of route changes observed there in the last hour were routes being removed. Start with the signals below.`,
  };
}


export default function RoutingHealth({
  globalStatus,
  attentionSignals,
  regionCount,
  ingestionHealth,
  updatedAt,
}) {
  const { headline, body } = describe({
    globalStatus,
    attentionSignals,
    regionCount,
    ageSeconds: ingestionHealth?.age_seconds,
  });

  const info = SEVERITY[globalStatus] || SEVERITY.normal;

  return (
    <section
      id="overview"
      className="health"
      style={{ "--health-color": info.color }}
      aria-labelledby="health-heading"
    >
      <p className="health__kicker">Global routing health</p>

      <div className="health__state">
        <StatusBadge severity={globalStatus} size="lg" />
      </div>

      <h1
        id="health-heading"
        className="health__headline"
        aria-live="polite"
      >
        {headline}
      </h1>

      <p className="health__body">{body}</p>

      <dl className="health__meta">
        <div>
          <dt>Source</dt>
          <dd>RIPE RIS Live</dd>
        </div>

        <div>
          <dt>Last event</dt>
          <dd>{formatAge(ingestionHealth?.age_seconds)}</dd>
        </div>

        <div>
          <dt>Window</dt>
          <dd>Last 60 minutes</dd>
        </div>

        <div>
          <dt>Page updated</dt>
          <dd>{updatedAt ? formatTime(updatedAt) : "—"}</dd>
        </div>
      </dl>

      <details className="method">
        <summary>How is this determined?</summary>

        <div className="method__body">
          <p>
            Interdomain uses a simple, transparent rule rather than a
            statistical model. For each region and each collector, it
            calculates the <strong>withdrawal share</strong>: the percentage
            of route changes in the last hour that removed a route (BGP
            withdrawals) rather than announced one.
          </p>

          <ul>
            <li>
              Fewer than {THRESHOLDS.minEvents} route changes: always
              Normal (too little data to judge).
            </li>
            <li>{THRESHOLDS.elevated}% or more: Elevated</li>
            <li>{THRESHOLDS.high}% or more: High</li>
            <li>{THRESHOLDS.critical}% or more: Critical</li>
          </ul>

          <p>
            The overall state is the most severe region, unless the data
            feed is delayed (no event for 15 seconds) or offline (none for
            60 seconds). There is no historical baseline yet, so a high
            share means “worth a look”, not “confirmed outage”.
          </p>
        </div>
      </details>
    </section>
  );
}
