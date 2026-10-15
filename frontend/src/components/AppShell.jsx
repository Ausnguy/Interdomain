import { useEffect, useState } from "react";

import StatusBadge from "./StatusBadge.jsx";
import { formatAge } from "../lib/format.js";


const NAV_ITEMS = [
  { id: "overview", label: "Overview" },
  { id: "signals", label: "Signals" },
  { id: "map", label: "Map" },
  { id: "activity", label: "Activity" },
  { id: "regions", label: "Regions" },
  { id: "technical", label: "Investigate" },
];


const FEED_STATUS = {
  live: { severity: "normal", label: "Live" },
  stale: { severity: "stale", label: "Delayed" },
  offline: { severity: "offline", label: "Offline" },
};


function useActiveSection() {
  const [active, setActive] = useState(NAV_ITEMS[0].id);

  useEffect(() => {
    const elements = NAV_ITEMS
      .map(({ id }) => document.getElementById(id))
      .filter(Boolean);

    // The active section is the last one whose top has passed a line 40%
    // down the viewport (the bottom of the observer band). The observer
    // only signals that something crossed; positions are re-read so fast
    // or smooth scrolls settle correctly.
    function update() {
      const line = window.innerHeight * 0.4;
      let current = elements[0];

      for (const element of elements) {
        if (element.getBoundingClientRect().top <= line) {
          current = element;
        }
      }

      if (current) {
        setActive(current.id);
      }
    }

    const observer = new IntersectionObserver(update, {
      threshold: [0, 1],
      rootMargin: "-35% 0px -60% 0px",
    });

    elements.forEach((element) => observer.observe(element));

    window.addEventListener("scrollend", update);

    return () => {
      observer.disconnect();
      window.removeEventListener("scrollend", update);
    };
  }, []);

  return active;
}


export default function AppShell({
  ingestionHealth,
  children,
}) {
  const active = useActiveSection();

  const feed =
    FEED_STATUS[ingestionHealth?.status] ||
    FEED_STATUS.offline;

  return (
    <div className="shell">
      <a className="skip-link" href="#main">
        Skip to content
      </a>

      <aside className="sidebar">
        <div className="brand">
          <span className="brand__name" translate="no">Interdomain</span>
          <span className="brand__tagline">
            Internet routing observability
          </span>
        </div>

        <nav className="nav" aria-label="Sections">
          <ul>
            {NAV_ITEMS.map(({ id, label }) => (
              <li key={id}>
                <a
                  href={`#${id}`}
                  className="nav__link"
                  aria-current={active === id ? "location" : undefined}
                >
                  {label}
                </a>
              </li>
            ))}
          </ul>
        </nav>

        <div className="feed">
          <span className="feed__label">RIPE RIS Live feed</span>
          <StatusBadge
            severity={feed.severity}
            label={feed.label}
            size="sm"
          />
          <span className="feed__age">
            Last event {formatAge(ingestionHealth?.age_seconds)}
          </span>
        </div>
      </aside>

      <main id="main" className="main" tabIndex={-1}>
        {children}
      </main>
    </div>
  );
}
