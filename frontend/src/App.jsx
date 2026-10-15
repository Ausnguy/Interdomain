import { useMemo } from "react";

// Leaflet's base styles must load before App.css so our overrides win.
import "leaflet/dist/leaflet.css";
import "./App.css";

import AppShell from "./components/AppShell.jsx";
import KeyMetrics from "./components/KeyMetrics.jsx";
import RegionalHealth from "./components/RegionalHealth.jsx";
import RoutingActivity from "./components/RoutingActivity.jsx";
import RoutingHealth from "./components/RoutingHealth.jsx";
import RoutingMap from "./components/RoutingMap.jsx";
import RoutingSignals from "./components/RoutingSignals.jsx";
import TechnicalSection from "./components/TechnicalSection.jsx";
import {
  API,
  POLL_INTERVAL_MS,
  useInterdomainData,
} from "./hooks/useInterdomainData.js";
import { COLLECTOR_LOCATIONS } from "./lib/collectors.js";
import { collectorId, formatTime } from "./lib/format.js";
import {
  compareSignals,
  deriveSignal,
  severityRank,
} from "./lib/signals.js";


const EMPTY = [];


function App() {
  const { data, error, updatedAt } = useInterdomainData();

  const regions = data?.regions ?? EMPTY;
  const collectors = data?.collectors ?? EMPTY;
  const ingestionHealth = data?.ingestionHealth;


  const regionSignals = useMemo(
    () =>
      regions
        .map((region) => ({
          ...region,
          ...deriveSignal(region),
        }))
        .sort(compareSignals),
    [regions]
  );


  const collectorRows = useMemo(
    () =>
      collectors
        .map((collector) => {
          const id = collectorId(collector.collector);
          const [city, country, lat, lng] =
            COLLECTOR_LOCATIONS[id] || [];

          return {
            ...collector,
            id,
            city,
            country,
            lat,
            lng,
            ...deriveSignal(collector),
          };
        })
        .sort(compareSignals),
    [collectors]
  );


  const mappedCollectors = useMemo(
    () => collectorRows.filter((collector) => collector.lat !== undefined),
    [collectorRows]
  );


  const attentionSignals = useMemo(
    () => regionSignals.filter((region) => region.severity !== "normal"),
    [regionSignals]
  );


  const globalStatus = useMemo(() => {
    const ingestionStatus = ingestionHealth?.status;

    if (ingestionStatus === "offline" || ingestionStatus === "stale") {
      return ingestionStatus;
    }

    return regionSignals.reduce(
      (current, region) =>
        severityRank(region.severity) > severityRank(current)
          ? region.severity
          : current,
      "normal"
    );
  }, [ingestionHealth, regionSignals]);


  const regionCount = regions.filter(
    (region) => region.region !== "unknown"
  ).length;


  if (!data) {
    return (
      <div className="loading" role="status">
        <span className="loading__dot" aria-hidden="true" />
        <p>
          {error
            ? `${error} Start the API (scripts/dev.ps1) — retrying every ${POLL_INTERVAL_MS / 1000} seconds.`
            : "Connecting to live routing data…"}
        </p>
      </div>
    );
  }


  return (
    <AppShell ingestionHealth={ingestionHealth}>
      {error && (
        <div className="error-banner" role="alert">
          <strong>{error}</strong>{" "}
          Showing data from {formatTime(updatedAt)}. Retrying every{" "}
          {POLL_INTERVAL_MS / 1000} seconds. Check that the API is running
          at {API}.
        </div>
      )}

      <RoutingHealth
        globalStatus={globalStatus}
        attentionSignals={attentionSignals}
        regionCount={regionCount}
        ingestionHealth={ingestionHealth}
        updatedAt={updatedAt}
      />

      <KeyMetrics
        summary={data.summary}
        regionCount={regionCount}
        collectorCount={collectors.length}
      />

      <RoutingSignals
        attentionSignals={attentionSignals}
        feedIsLive={ingestionHealth?.status === "live"}
      />

      <RoutingMap
        mappedCollectors={mappedCollectors}
        unmappedCount={collectorRows.length - mappedCollectors.length}
      />

      <RoutingActivity activity={data.activity} />

      <RegionalHealth regionSignals={regionSignals} />

      <TechnicalSection
        asns={data.asns}
        withdrawals={data.withdrawals}
        routes={data.routes}
        collectorRows={collectorRows}
      />

      <footer className="footer">
        <span>Interdomain: global BGP routing observability</span>
        <span>
          Data from RIPE NCC Routing Information Service (RIS)
        </span>
      </footer>
    </AppShell>
  );
}


export default App;
