import { useEffect, useState } from "react";


// Set VITE_API_URL at build time. The container build uses "/api" so the
// browser talks to the same origin and nginx forwards to the API.
export const API = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000";

export const POLL_INTERVAL_MS = 5000;


const ENDPOINTS = {
  summary: "/metrics/summary",
  routes: "/routes/recent?limit=15",
  withdrawals: "/routes/withdrawals?limit=8",
  asns: "/asns/active?limit=8",
  regions: "/regions/summary",
  collectors: "/collectors/activity",
  activity: "/metrics/activity",
  ingestionHealth: "/health/ingestion",
};


// Polls every endpoint in parallel. A refresh is all-or-nothing: if any
// request fails, the last good snapshot stays on screen and `error` is set.
export function useInterdomainData() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [updatedAt, setUpdatedAt] = useState(null);


  useEffect(() => {
    let cancelled = false;
    let inFlight = false;

    const keys = Object.keys(ENDPOINTS);


    async function loadData() {
      const responses = await Promise.all(
        keys.map((key) =>
          fetch(`${API}${ENDPOINTS[key]}`)
        )
      );

      if (responses.some((response) => !response.ok)) {
        throw new Error("API request failed");
      }

      const bodies = await Promise.all(
        responses.map((response) => response.json())
      );

      if (cancelled) {
        return;
      }

      setData(
        Object.fromEntries(
          keys.map((key, index) => [key, bodies[index]])
        )
      );

      setUpdatedAt(new Date());
      setError(null);
    }


    function refresh() {
      // Skip a tick rather than stack requests behind a slow API, and
      // stop polling while the tab is hidden.
      if (inFlight || document.hidden) {
        return;
      }

      inFlight = true;

      loadData()
        .catch((err) => {
          if (cancelled) {
            return;
          }

          console.error(err);

          setError(
            `Can't reach the Interdomain API at ${API}.`
          );
        })
        .finally(() => {
          inFlight = false;
        });
    }


    function handleVisibility() {
      if (!document.hidden) {
        refresh();
      }
    }


    refresh();

    const interval = setInterval(refresh, POLL_INTERVAL_MS);

    document.addEventListener("visibilitychange", handleVisibility);


    return () => {
      cancelled = true;
      clearInterval(interval);
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, []);


  return {
    data,
    error,
    updatedAt,
  };
}
