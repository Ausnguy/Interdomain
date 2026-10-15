-- Fresh-install schema. Existing databases upgrade with
-- sql/migrations/003_rollups_partitioning.sql.

-- Raw BGP events, partitioned by insert hour and kept for
-- RAW_RETENTION_HOURS. Partitions are created ahead of time by the consumer
-- and scripts/run_maintenance.py; old ones are dropped, not deleted from.
CREATE TABLE IF NOT EXISTS bgp_events (
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

CREATE INDEX IF NOT EXISTS idx_bgp_events_observed_at
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


-- Per-minute counts by collector and peer: the source for every dashboard
-- count, region, collector, ASN and activity metric.
CREATE TABLE IF NOT EXISTS bgp_minute_stats (
    minute TIMESTAMPTZ NOT NULL,
    collector TEXT NOT NULL,
    collector_region TEXT NOT NULL,
    peer_asn BIGINT NOT NULL,          -- 0 = unknown
    announcements BIGINT NOT NULL DEFAULT 0,
    withdrawals BIGINT NOT NULL DEFAULT 0,
    PRIMARY KEY (minute, collector, peer_asn)
);


-- When each collector last saw each prefix (minute precision), for exact
-- distinct-prefix counts.
CREATE TABLE IF NOT EXISTS bgp_prefix_seen (
    collector TEXT NOT NULL,
    prefix CIDR NOT NULL,
    collector_region TEXT NOT NULL,
    last_seen TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (collector, prefix)
) WITH (fillfactor = 80);


-- Distinct-prefix counts for the dashboard window, refreshed every 30 s.
CREATE TABLE IF NOT EXISTS bgp_prefix_counts (
    scope TEXT NOT NULL CHECK (scope IN ('global', 'region', 'collector')),
    key TEXT NOT NULL,
    unique_prefixes BIGINT NOT NULL,
    computed_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (scope, key)
);


-- Next Kafka offset per partition, committed with each batch.
CREATE TABLE IF NOT EXISTS kafka_offsets (
    topic TEXT NOT NULL,
    partition INT NOT NULL,
    next_offset BIGINT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (topic, partition)
);
