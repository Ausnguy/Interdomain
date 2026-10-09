SELECT prefix, COUNT(*) AS withdrawal_count
FROM bgp_events
WHERE event_type = 'withdrawal' AND observed_at >= NOW() - INTERVAL '1 hour'
GROUP BY prefix
ORDER BY withdrawal_count DESC
LIMIT 20;
