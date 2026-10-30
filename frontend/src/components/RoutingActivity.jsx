import { useMemo } from "react";

import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import Section from "./Section.jsx";
import {
  formatClock,
  formatNumber,
} from "../lib/format.js";


const RECENT_MINUTES = 5;


function median(values) {
  if (values.length === 0) {
    return 0;
  }

  const sorted = values.toSorted((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);

  return sorted.length % 2
    ? sorted[middle]
    : (sorted[middle - 1] + sorted[middle]) / 2;
}


// A plain-language answer to "is activity changing abnormally?", compared
// against this hour only. The current minute is still filling, so skip it.
function summarize(activity) {
  const complete = activity.slice(0, -1);
  const updates = complete.map((point) => Number(point.updates));
  const total = updates.reduce((sum, value) => sum + value, 0);

  if (total === 0) {
    return {
      median: 0,
      text: "No route changes were recorded in the last hour.",
    };
  }

  const hourMedian = median(updates);
  const recent = updates.slice(-RECENT_MINUTES);
  const recentAvg =
    recent.reduce((sum, value) => sum + value, 0) /
    Math.max(recent.length, 1);

  if (recentAvg === 0) {
    return {
      median: hourMedian,
      text: `No route changes were recorded in the last ${RECENT_MINUTES} minutes. The hour's total was ${formatNumber(total)}.`,
    };
  }

  let comparison = "about the same as";

  if (hourMedian > 0) {
    const ratio = recentAvg / hourMedian;

    if (ratio >= 1.5) {
      comparison = `${ratio.toFixed(1)}× higher than`;
    } else if (ratio <= 0.5) {
      comparison = "well below";
    }
  }

  return {
    median: hourMedian,
    text: `Over the last ${RECENT_MINUTES} minutes, routing averaged ${formatNumber(Math.round(recentAvg))} changes per minute, ${comparison} the hour's median of ${formatNumber(Math.round(hourMedian))}.`,
  };
}


function ActivityTooltip({ active, payload, label }) {
  if (!active || !payload?.length) {
    return null;
  }

  const point = payload[0].payload;

  return (
    <div className="chart-tooltip">
      <p className="chart-tooltip__title">{formatClock(label)}</p>
      <p>{formatNumber(point.updates)} route changes</p>
      <p>{formatNumber(point.withdrawals)} withdrawals</p>
    </div>
  );
}


export default function RoutingActivity({ activity }) {
  const summary = useMemo(() => summarize(activity), [activity]);

  return (
    <Section
      id="activity"
      title="How activity is changing"
      description="Route changes per minute over the last hour, with withdrawals shown separately."
    >
      <p className="activity__summary">{summary.text}</p>

      <div className="chart-key" aria-hidden="true">
        <span className="chart-key__item">
          <i className="chart-key__line chart-key__line--updates" />
          Route changes
        </span>
        <span className="chart-key__item">
          <i className="chart-key__line chart-key__line--withdrawals" />
          Withdrawals
        </span>
        <span className="chart-key__item">
          <i className="chart-key__line chart-key__line--median" />
          1-hour median
        </span>
      </div>

      <div
        className="activity__chart"
        role="img"
        aria-label={`Line chart of route changes per minute. ${summary.text}`}
      >
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={activity}
            margin={{ top: 8, right: 8, bottom: 0, left: 0 }}
          >
            <CartesianGrid
              vertical={false}
              stroke="var(--line)"
            />

            <XAxis
              dataKey="minute"
              tickFormatter={formatClock}
              tickLine={false}
              axisLine={{ stroke: "var(--line)" }}
              minTickGap={48}
              tick={{ fill: "var(--ink-3)", fontSize: 12 }}
            />

            <YAxis
              width={48}
              tickLine={false}
              axisLine={false}
              tickFormatter={formatNumber}
              tick={{ fill: "var(--ink-3)", fontSize: 12 }}
            />

            <Tooltip
              content={<ActivityTooltip />}
              cursor={{ stroke: "var(--ink-3)", strokeDasharray: "2 2" }}
            />

            {summary.median > 0 && (
              <ReferenceLine
                y={summary.median}
                stroke="var(--ink-3)"
                strokeDasharray="4 4"
              />
            )}

            <Line
              type="monotone"
              dataKey="updates"
              name="Route changes"
              stroke="var(--chart-primary)"
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />

            <Line
              type="monotone"
              dataKey="withdrawals"
              name="Withdrawals"
              stroke="var(--sev-critical)"
              strokeWidth={1.5}
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </Section>
  );
}
