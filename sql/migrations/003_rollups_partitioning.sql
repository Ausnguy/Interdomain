-- Pre-aggregated dashboard tables and an hourly-partitioned raw event table.
--
-- Run with the Kafka consumer stopped. The existing table is kept as
-- bgp_events_legacy so the new endpoints can be checked against it; drop it
-- afterwards with: DROP TABLE bgp_events_legacy;

BEGIN;

-- 1. Move the existing raw table aside.
ALTER TABLE bgp_events RENAME TO bgp_events_legacy;
ALTER INDEX idx_bgp_events_observed_at RENAME TO idx_bgp_events_legacy_observed_at;


-- 2. Raw events, partitioned by insert hour. Only the observed_at index is
--    kept: aggregate queries now read the rollup tables.
CREATE TABLE bgp_events (
    observed_at TIMESTAMPTZ NOT NULL,

    peer TEXT,
    peer_asn BIGINT,

    collector TEXT,
    collector_region TEXT NOT NULL DEFAULT 'unknown',

    prefix CIDR NOT NULL,

    event_type TEXT NOT NULL
        CHECK (event_type IN ('announcement', 'withdrawal')),

    as_path BIGINT[],
    next_hop INET,

    inserted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
) PARTITION BY RANGE (inserted_at);

CREATE INDEX idx_bgp_events_observed_at
    ON bgp_events (observed_at DESC);

DO $$
DECLARE
    hour_start TIMESTAMP := date_trunc('hour', NOW() AT TIME ZONE 'UTC');
    i INT;
BEGIN
    FOR i IN 0..3 LOOP
        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS %I PARTITION OF bgp_events FOR VALUES FROM (%L) TO (%L)',
            'bgp_events_p' || to_char(hour_start + make_interval(hours => i), 'YYYYMMDDHH24'),
            to_char(hour_start + make_interval(hours => i), 'YYYY-MM-DD HH24:00:00+00'),
            to_char(hour_start + make_interval(hours => i + 1), 'YYYY-MM-DD HH24:00:00+00')
        );
    END LOOP;
END $$;


-- 3. Per-minute counts by collector and peer: the source for every
--    dashboard count, region, collector, ASN and activity metric.
CREATE TABLE bgp_minute_stats (
    minute TIMESTAMPTZ NOT NULL,
    collector TEXT NOT NULL,
    collector_region TEXT NOT NULL,
    peer_asn BIGINT NOT NULL,          -- 0 = unknown
    announcements BIGINT NOT NULL DEFAULT 0,
    withdrawals BIGINT NOT NULL DEFAULT 0,
    PRIMARY KEY (minute, collector, peer_asn)
);


-- 4. When each collector last saw each prefix (minute precision), for
--    exact distinct-prefix counts.
CREATE TABLE bgp_prefix_seen (
    collector TEXT NOT NULL,
    prefix CIDR NOT NULL,
    collector_region TEXT NOT NULL,
    last_seen TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (collector, prefix)
) WITH (fillfactor = 80);


-- 5. Distinct-prefix counts for the dashboard window, refreshed every 30 s
--    by scripts/run_maintenance.py.
CREATE TABLE bgp_prefix_counts (
    scope TEXT NOT NULL CHECK (scope IN ('global', 'region', 'collector')),
    key TEXT NOT NULL,
    unique_prefixes BIGINT NOT NULL,
    computed_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (scope, key)
);


-- 6. Next Kafka offset per partition, committed with each batch so the
--    consumer resumes exactly where Postgres left off.
CREATE TABLE kafka_offsets (
    topic TEXT NOT NULL,
    partition INT NOT NULL,
    next_offset BIGINT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (topic, partition)
);


-- 7. Backfill the rollups from the last hour of legacy events so the
--    dashboard is complete immediately.
INSERT INTO bgp_minute_stats (
    minute,
    collector,
    collector_region,
    peer_asn,
    announcements,
    withdrawals
)
SELECT
    date_trunc('minute', observed_at),
    COALESCE(collector, 'unknown'),
    MIN(collector_region),
    COALESCE(peer_asn, 0),
    COUNT(*) FILTER (WHERE event_type = 'announcement'),
    COUNT(*) FILTER (WHERE event_type = 'withdrawal')
FROM bgp_events_legacy
WHERE observed_at >= date_trunc('minute', NOW()) - INTERVAL '60 minutes'
GROUP BY 1, 2, 4;

INSERT INTO bgp_prefix_seen (
    collector,
    prefix,
    collector_region,
    last_seen
)
SELECT
    COALESCE(collector, 'unknown'),
    prefix,
    MIN(collector_region),
    MAX(observed_at)
FROM bgp_events_legacy
WHERE observed_at >= NOW() - INTERVAL '65 minutes'
GROUP BY 1, 2;

COMMIT;
