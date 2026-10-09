import { useEffect, useState } from "react";

import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

import "./App.css";

const API = "http://127.0.0.1:8000";

function App() {
  const [activeSection, setActiveSection] = useState("overview");

  const [summary, setSummary] = useState(null);
  const [routes, setRoutes] = useState([]);
  const [withdrawals, setWithdrawals] = useState([]);
  const [asns, setAsns] = useState([]);

  const [activity, setActivity] = useState([]);
  const [ingestionHealth, setIngestionHealth] = useState(null);

  const [error, setError] = useState(null);
  const [updatedAt, setUpdatedAt] = useState(null);

  function scrollToSection(section) {
    setActiveSection(section);

    const element = document.getElementById(section);

    if (element) {
      element.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    }
  }

  useEffect(() => {
    let cancelled = false;

    async function loadData() {
      const [
        summaryRes,
        routesRes,
        withdrawalsRes,
        asnsRes,
        activityRes,
        healthRes,
      ] = await Promise.all([
        fetch(`${API}/metrics/summary`),
        fetch(`${API}/routes/recent?limit=12`),
        fetch(`${API}/routes/withdrawals?limit=8`),
        fetch(`${API}/asns/active?limit=8`),
        fetch(`${API}/metrics/activity`),
        fetch(`${API}/health/ingestion`),
      ]);

      if (
        !summaryRes.ok ||
        !routesRes.ok ||
        !withdrawalsRes.ok ||
        !asnsRes.ok ||
        !activityRes.ok ||
        !healthRes.ok
      ) {
        throw new Error("API request failed");
      }

      const [
        summaryData,
        routesData,
        withdrawalsData,
        asnsData,
        activityData,
        healthData,
      ] = await Promise.all([
        summaryRes.json(),
        routesRes.json(),
        withdrawalsRes.json(),
        asnsRes.json(),
        activityRes.json(),
        healthRes.json(),
      ]);

      if (cancelled) return;

      setSummary(summaryData);
      setRoutes(routesData);
      setWithdrawals(withdrawalsData);
      setAsns(asnsData);

      setActivity(activityData);
      setIngestionHealth(healthData);

      setUpdatedAt(new Date());
      setError(null);
    }

    function refreshData() {
      loadData().catch((err) => {
        if (cancelled) return;

        console.error(err);
        setError("Unable to reach Interdomain API.");
      });
    }

    refreshData();

    const interval = setInterval(refreshData, 5000);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  if (!summary) {
    return (
      <div className="loading-screen">
        <div className="loading-dot" />
        <span>{error || "Connecting to Interdomain..."}</span>
      </div>
    );
  }

  const streamStatus = ingestionHealth?.status || "offline";

  return (
    <div className="app">
      <aside className="sidebar">
        <div>
          <div className="brand">
            <div className="brand-mark">I</div>

            <div>
              <h1>Interdomain</h1>
              <span>Routing Observatory</span>
            </div>
          </div>

          <nav>
            <button
              className={`nav-item ${
                activeSection === "overview" ? "active" : ""
              }`}
              onClick={() => scrollToSection("overview")}
            >
              Overview
            </button>

            <button
              className={`nav-item ${
                activeSection === "routes" ? "active" : ""
              }`}
              onClick={() => scrollToSection("routes")}
            >
              Routes
            </button>

            <button
              className={`nav-item ${
                activeSection === "asns" ? "active" : ""
              }`}
              onClick={() => scrollToSection("asns")}
            >
              Autonomous Systems
            </button>

            <button
              className={`nav-item ${
                activeSection === "withdrawals" ? "active" : ""
              }`}
              onClick={() => scrollToSection("withdrawals")}
            >
              Withdrawals
            </button>
          </nav>
        </div>

        <div className="sidebar-footer">
          <div className="status-row">
            <span className={`status-dot ${streamStatus}`} />

            RIPE RIS Live
          </div>

          <span className="small-text">
            {streamStatus === "live"
              ? "Streaming operational"
              : streamStatus === "stale"
                ? "Stream appears stale"
                : "Ingestion offline"}
          </span>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <p className="eyebrow">
              INTERNET ROUTING OBSERVABILITY
            </p>

            <h2>Network Overview</h2>
          </div>

          <div className={`live-pill ${streamStatus}`}>
            <span className="status-dot" />

            {streamStatus.toUpperCase()}
          </div>
        </header>

        {error && (
          <div className="error-banner">
            {error}
          </div>
        )}

        <section id="overview" className="metrics-grid">
          <MetricCard
            label="Routing Updates"
            value={summary.total_events}
            detail="Last hour"
          />

          <MetricCard
            label="Announcements"
            value={summary.announcements}
            detail="Routes advertised"
          />

          <MetricCard
            label="Withdrawals"
            value={summary.withdrawals}
            detail="Routes removed"
            warning
          />

          <MetricCard
            label="Observed Prefixes"
            value={summary.unique_prefixes}
            detail={`${summary.unique_peer_asns} peer ASNs`}
          />
        </section>

        <section className="panel activity-panel">
          <div className="panel-header">
            <div>
              <p className="panel-label">
                STREAM ACTIVITY
              </p>

              <h3>BGP Updates Per Minute</h3>
            </div>

            <span className="muted">
              Last 60 minutes
            </span>
          </div>

          <div className="activity-chart">
            <ResponsiveContainer
              width="100%"
              height="100%"
            >
              <LineChart
                data={activity}
                margin={{
                  top: 5,
                  right: 10,
                  bottom: 5,
                  left: 0,
                }}
              >
                <XAxis
                  dataKey="minute"
                  tickFormatter={(value) =>
                    new Date(
                      value
                    ).toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                    })
                  }
                  tickLine={false}
                  axisLine={false}
                  minTickGap={40}
                  tick={{
                    fill: "#68727f",
                    fontSize: 10,
                  }}
                />

                <YAxis
                  tickLine={false}
                  axisLine={false}
                  width={40}
                  tick={{
                    fill: "#68727f",
                    fontSize: 10,
                  }}
                />

                <Tooltip
                  labelFormatter={(value) =>
                    new Date(
                      value
                    ).toLocaleTimeString()
                  }
                  contentStyle={{
                    background: "#12161c",
                    border: "1px solid #252b34",
                    borderRadius: "8px",
                  }}
                />

                <Line
                  type="monotone"
                  dataKey="updates"
                  stroke="#e7edf5"
                  strokeWidth={2}
                  dot={false}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </section>

        <section className="content-grid">
          <div
            id="asns"
            className="panel chart-panel"
          >
            <div className="panel-header">
              <div>
                <p className="panel-label">
                  ROUTING ACTIVITY
                </p>

                <h3>Most Active Peer ASNs</h3>
              </div>

              <span className="muted">
                Last hour
              </span>
            </div>

            <div className="chart">
              <ResponsiveContainer
                width="100%"
                height="100%"
              >
                <BarChart
                  data={asns}
                  layout="vertical"
                  margin={{
                    top: 4,
                    right: 12,
                    bottom: 4,
                    left: 10,
                  }}
                >
                  <XAxis
                    type="number"
                    tickLine={false}
                    axisLine={false}
                    tick={{
                      fill: "#7f8997",
                      fontSize: 12,
                    }}
                  />

                  <YAxis
                    type="category"
                    dataKey="peer_asn"
                    tickFormatter={(value) =>
                      `AS${value}`
                    }
                    tickLine={false}
                    axisLine={false}
                    width={80}
                    tick={{
                      fill: "#aeb7c4",
                      fontSize: 12,
                    }}
                  />

                  <Tooltip
                    cursor={{
                      fill:
                        "rgba(255,255,255,0.025)",
                    }}
                    contentStyle={{
                      background: "#12161c",
                      border:
                        "1px solid #252b34",
                      borderRadius: "8px",
                    }}
                    labelFormatter={(value) =>
                      `AS${value}`
                    }
                  />

                  <Bar
                    dataKey="update_count"
                    fill="#e7edf5"
                    radius={[0, 4, 4, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div
            id="withdrawals"
            className="panel withdrawals-panel"
          >
            <div className="panel-header">
              <div>
                <p className="panel-label">
                  CONTROL PLANE
                </p>

                <h3>Recent Withdrawals</h3>
              </div>

              <span className="count-badge">
                {withdrawals.length}
              </span>
            </div>

            <div className="withdrawal-list">
              {withdrawals.map(
                (item, index) => (
                  <div
                    className="withdrawal-item"
                    key={`${item.prefix}-${index}`}
                  >
                    <div>
                      <div className="prefix">
                        {item.prefix}
                      </div>

                      <div className="muted">
                        AS
                        {item.peer_asn ?? "—"}
                      </div>
                    </div>

                    <div className="withdrawal-badge">
                      WITHDRAWN
                    </div>
                  </div>
                )
              )}
            </div>
          </div>
        </section>

        <section
          id="routes"
          className="panel routes-panel"
        >
          <div className="panel-header">
            <div>
              <p className="panel-label">
                LIVE FEED
              </p>

              <h3>Recent Routing Events</h3>
            </div>

            <div className="refresh">
              Auto-refresh · 5s
            </div>
          </div>

          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Event</th>
                  <th>Prefix</th>
                  <th>Peer ASN</th>
                  <th>Next Hop</th>
                  <th>Observed</th>
                </tr>
              </thead>

              <tbody>
                {routes.map((route, index) => (
                  <tr
                    key={`${route.prefix}-${route.observed_at}-${index}`}
                  >
                    <td>
                      <span
                        className={`event-badge ${
                          route.event_type ===
                          "withdrawal"
                            ? "withdrawal"
                            : "announcement"
                        }`}
                      >
                        {route.event_type}
                      </span>
                    </td>

                    <td className="mono">
                      {route.prefix}
                    </td>

                    <td className="mono">
                      {route.peer_asn
                        ? `AS${route.peer_asn}`
                        : "—"}
                    </td>

                    <td className="mono muted">
                      {route.next_hop || "—"}
                    </td>

                    <td className="muted">
                      {formatTime(
                        route.observed_at
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <footer>
          <span>
            Interdomain · Real-time BGP
            routing observability
          </span>

          <span>
            {updatedAt
              ? `Updated ${updatedAt.toLocaleTimeString()}`
              : ""}
          </span>
        </footer>
      </main>
    </div>
  );
}

function MetricCard({
  label,
  value,
  detail,
  warning = false,
}) {
  return (
    <div className="metric-card">
      <div className="metric-label">
        {label}
      </div>

      <div
        className={
          warning
            ? "metric-value warning"
            : "metric-value"
        }
      >
        {Number(value).toLocaleString()}
      </div>

      <div className="metric-detail">
        {detail}
      </div>
    </div>
  );
}

function formatTime(value) {
  if (!value) return "—";

  return new Date(value).toLocaleTimeString(
    [],
    {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    }
  );
}

export default App;