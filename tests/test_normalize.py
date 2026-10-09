from interdomain.processing.normalize import normalize_bgp_event


def test_normalizes_announcement_and_withdrawal():
    event = {
        "timestamp": 1700000000,
        "peer": "192.0.2.1",
        "peer_asn": 64500,
        "path": [64500, 64496],
        "announcements": [{"next_hop": "192.0.2.2", "prefixes": ["203.0.113.0/24"]}],
        "withdrawals": ["198.51.100.0/24"],
    }
    rows = normalize_bgp_event(event)
    assert len(rows) == 2
    assert rows[0]["event_type"] == "announcement"
    assert rows[1]["event_type"] == "withdrawal"
