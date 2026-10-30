ALTER TABLE bgp_events
ADD COLUMN IF NOT EXISTS collector TEXT;

ALTER TABLE bgp_events
ADD COLUMN IF NOT EXISTS collector_region TEXT NOT NULL DEFAULT 'unknown';

CREATE INDEX IF NOT EXISTS idx_bgp_events_collector
ON bgp_events (collector);

CREATE INDEX IF NOT EXISTS idx_bgp_events_collector_region
ON bgp_events (collector_region);