CREATE TABLE IF NOT EXISTS bgp_events (
    id BIGSERIAL PRIMARY KEY,
    observed_at TIMESTAMPTZ NOT NULL,
    peer TEXT,
    peer_asn BIGINT,
    prefix CIDR NOT NULL,
    event_type TEXT NOT NULL CHECK (event_type IN ('announcement', 'withdrawal')),
    as_path BIGINT[],
    next_hop INET,
    inserted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_bgp_events_observed_at ON bgp_events (observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_bgp_events_event_type ON bgp_events (event_type);
CREATE INDEX IF NOT EXISTS idx_bgp_events_peer_asn ON bgp_events (peer_asn);
