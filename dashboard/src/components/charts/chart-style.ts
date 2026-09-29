import { formatDublinTime } from "@/lib/format-time";
import { ROAD_USER_CLASSES, type RoadUserClass } from "@/lib/types";

// Okabe–Ito (colour-blind safe), one colour per class in wire order.
const SERIES_COLOURS = [
  "#e69f00",
  "#56b4e9",
  "#009e73",
  "#f0e442",
  "#0072b2",
  "#d55e00",
  "#cc79a7",
  "#999999",
  "var(--ink-1)",
];

export const CLASS_COLOURS = Object.fromEntries(
  ROAD_USER_CLASSES.map((cls, i) => [cls, SERIES_COLOURS[i]!]),
) as Record<RoadUserClass, string>;

export const TOOLTIP_STYLE = {
  contentStyle: {
    background: "var(--surface)",
    borderRadius: 6,
    border: "1px solid var(--line)",
    color: "var(--ink-1)",
    fontSize: 12,
  },
  labelStyle: { color: "var(--ink-1)" },
  itemStyle: { color: "var(--ink-1)" },
};

/** Runs of offline buckets as [first, last] x values, for grey chart bands. */
export function offlineRanges<T extends { missing: boolean }, X>(rows: T[], x: (row: T) => X): [X, X][] {
  const out: [X, X][] = [];
  let start: X | null = null;
  rows.forEach((row, i) => {
    if (row.missing && start === null) start = x(row);
    const next = rows[i + 1];
    if (start !== null && row.missing && (!next || !next.missing)) {
      out.push([start, x(row)]);
      start = null;
    }
  });
  return out;
}

export const OFFLINE_FILL = "var(--line)";
export const BUCKET_MS = 15 * 60_000;

/** Shared time axis: x is the bucket start in ms, labelled in Dublin time. */
export const TIME_AXIS = {
  dataKey: "x",
  type: "number" as const,
  scale: "time" as const,
  domain: ["dataMin", "dataMax"] as [string, string],
  tickFormatter: (ms: number) => formatDublinTime(ms),
  stroke: "var(--ink-2)",
  fontSize: 12,
  tickMargin: 8,
};

export const timeLabel = (ms: unknown) => formatDublinTime(Number(ms));
