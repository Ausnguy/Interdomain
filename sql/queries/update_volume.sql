SELECT date_trunc('minute', observed_at) AS minute, COUNT(*) AS updates
FROM bgp_events
WHERE observed_at >= NOW() - INTERVAL '1 hour'
GROUP BY 1
ORDER BY 1;
