SELECT peer_asn, COUNT(*) AS update_count
FROM bgp_events
WHERE observed_at >= NOW() - INTERVAL '1 hour'
GROUP BY peer_asn
ORDER BY update_count DESC
LIMIT 20;
