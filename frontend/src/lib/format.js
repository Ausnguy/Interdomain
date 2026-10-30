export const REGION_NAMES = {
  north_america: "North America",
  latin_america: "Latin America",
  europe: "Europe",
  africa: "Africa",
  asia_pacific: "Asia Pacific",
  middle_east: "Middle East",
  global: "Global",
  unknown: "Unknown",
};


export function formatRegion(region) {
  return (
    REGION_NAMES[region] ||
    region ||
    "Unknown"
  );
}


export function collectorId(collector) {
  return (
    collector
      ?.toLowerCase()
      .split(".")[0] ||
    ""
  );
}


export function formatNumber(value) {
  return Number(value || 0).toLocaleString();
}


export function formatPct(value, digits = 1) {
  return `${Number(value || 0).toFixed(digits)}%`;
}


export function formatTime(value) {
  if (!value) {
    return "—";
  }

  return new Date(value).toLocaleTimeString(
    [],
    {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    }
  );
}


export function formatClock(value) {
  return new Date(value).toLocaleTimeString(
    [],
    {
      hour: "2-digit",
      minute: "2-digit",
    }
  );
}


export function formatAge(seconds) {
  if (
    seconds === null ||
    seconds === undefined
  ) {
    return "unknown";
  }

  if (seconds < 5) {
    return "just now";
  }

  if (seconds < 60) {
    return `${Math.round(seconds)}s ago`;
  }

  if (seconds < 3600) {
    return `${Math.round(seconds / 60)} min ago`;
  }

  if (seconds < 86400) {
    return `${Math.round(seconds / 3600)} h ago`;
  }

  return `${Math.round(seconds / 86400)} d ago`;
}


export function formatAsn(asn) {
  return asn === null || asn === undefined
    ? "—"
    : `AS${asn}`;
}


export function formatAsPath(path) {
  if (!Array.isArray(path) || path.length === 0) {
    return "—";
  }

  return path.join(" ");
}


export function joinNames(names) {
  if (names.length <= 1) {
    return names[0] || "";
  }

  if (names.length === 2) {
    return `${names[0]} and ${names[1]}`;
  }

  return `${names.slice(0, -1).join(", ")} and ${names.at(-1)}`;
}
