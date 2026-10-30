import {
  CircleMarker,
  MapContainer,
  TileLayer,
  Tooltip as MapTooltip,
} from "react-leaflet";

import Section from "./Section.jsx";
import {
  SEVERITY,
  SIGNAL_LEVELS,
} from "../lib/signals.js";
import {
  formatNumber,
  formatPct,
  formatRegion,
} from "../lib/format.js";


// Standard OSM tiles, muted with a CSS filter on the tile pane (see
// .routing-map .leaflet-tile-pane) so the severity colors stay readable.
// CARTO's muted basemaps now require an API key.
const TILE_URL = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";

const ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';


export default function RoutingMap({
  mappedCollectors,
  unmappedCount,
}) {
  const maxEvents = Math.max(
    ...mappedCollectors.map((collector) =>
      Number(collector.total_events)
    ),
    1
  );

  return (
    <Section
      id="map"
      title="Where it is being observed"
      description="Each circle is a RIPE RIS route collector: a router that listens to BGP updates from many networks. Its position shows where the activity was observed, not where the affected networks are located."
    >
      <div className="map-key" aria-hidden="true">
        <div className="map-key__group">
          <span className="map-key__title">Color</span>
          {SIGNAL_LEVELS.map((level) => (
            <span className="map-key__item" key={level}>
              <i
                className="map-key__swatch"
                style={{ background: SEVERITY[level].color }}
              />
              {SEVERITY[level].label}
            </span>
          ))}
        </div>

        <div className="map-key__group">
          <span className="map-key__title">Size</span>
          <span className="map-key__item">
            <i className="map-key__size map-key__size--sm" />
            <i className="map-key__size map-key__size--lg" />
            More route changes
          </span>
        </div>
      </div>

      <div
        className="map-frame"
        role="region"
        aria-label="World map of RIPE RIS collectors, colored by withdrawal severity"
      >
        <MapContainer
          center={[22, 10]}
          zoom={2}
          minZoom={2}
          maxZoom={7}
          worldCopyJump
          scrollWheelZoom={false}
          className="routing-map"
        >
          <TileLayer
            attribution={ATTRIBUTION}
            url={TILE_URL}
          />

          {mappedCollectors.map((collector) => {
            const events = Number(collector.total_events);
            const radius = 6 + Math.sqrt(events / maxEvents) * 18;
            const info = SEVERITY[collector.severity];

            return (
              <CircleMarker
                key={collector.collector}
                center={[collector.lat, collector.lng]}
                radius={radius}
                pathOptions={{
                  color: info.color,
                  fillColor: info.color,
                  fillOpacity: 0.35,
                  opacity: 0.9,
                  weight: 1.5,
                }}
              >
                <MapTooltip direction="top" offset={[0, -radius]}>
                  <div className="map-tooltip">
                    <p className="map-tooltip__title">
                      <span className="mono">{collector.id.toUpperCase()}</span>
                      <span>{info.label}</span>
                    </p>
                    <p className="map-tooltip__place">
                      {collector.city}, {collector.country}
                    </p>
                    <dl>
                      <dt>Route changes</dt>
                      <dd>{formatNumber(events)}</dd>
                      <dt>Announcements</dt>
                      <dd>{formatNumber(collector.announcements)}</dd>
                      <dt>Withdrawals</dt>
                      <dd>{formatNumber(collector.withdrawals)}</dd>
                      <dt>Withdrawal share</dt>
                      <dd>{formatPct(collector.withdrawalRate)}</dd>
                      <dt>Region</dt>
                      <dd>{formatRegion(collector.collector_region)}</dd>
                    </dl>
                  </div>
                </MapTooltip>
              </CircleMarker>
            );
          })}
        </MapContainer>
      </div>

      <p className="section__footnote">
        Scroll the page normally; use the + and − buttons to zoom. The same
        data is listed in the{" "}
        <a href="#collectors">collectors table</a>.
        {unmappedCount > 0 &&
          ` ${unmappedCount} ${unmappedCount === 1 ? "collector has" : "collectors have"} no known location and ${unmappedCount === 1 ? "is" : "are"} not shown on the map.`}
      </p>
    </Section>
  );
}
