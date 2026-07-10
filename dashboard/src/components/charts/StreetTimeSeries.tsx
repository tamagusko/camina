"use client";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ROAD_USER_CLASSES, type RoadUserClass, type StreetReading } from "@/lib/types";
import { formatDublinTime } from "@/lib/format-time";

interface Props {
  readings: StreetReading[];
}

// DESIGN.md-aligned greys so the chart doesn't inject brand colour — we only
// differentiate classes by ramp position (not hue). Class names stay in the
// legend for clarity.
const SERIES_COLOURS = [
  "#000000",
  "#4b4b4b",
  "#6e6e6e",
  "#8a8a8a",
  "#a5a5a5",
  "#c0c0c0",
  "#d4d4d4",
  "#e2e2e2",
  "#efefef",
];

export function StreetTimeSeries({ readings }: Props) {
  if (readings.length === 0) {
    return (
      <div className="card flex h-64 items-center justify-center text-body-gray">
        No data in the selected window
      </div>
    );
  }
  const data = readings.map((r) => ({
    t: formatDublinTime(r.bucket),
    ...r.counts,
  }));

  return (
    <div className="card p-6">
      <ResponsiveContainer width="100%" height={320}>
        <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 8, left: 0 }}>
          <CartesianGrid stroke="#efefef" vertical={false} />
          <XAxis dataKey="t" stroke="#4b4b4b" fontSize={12} tickMargin={8} />
          <YAxis stroke="#4b4b4b" fontSize={12} tickMargin={8} allowDecimals={false} />
          <Tooltip
            contentStyle={{ borderRadius: 8, border: "1px solid #000", fontSize: 12 }}
            labelStyle={{ color: "#000" }}
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          {ROAD_USER_CLASSES.map((cls: RoadUserClass, i) => (
            <Area
              key={cls}
              type="monotone"
              dataKey={cls}
              stackId="counts"
              stroke={SERIES_COLOURS[i]}
              fill={SERIES_COLOURS[i]}
              fillOpacity={0.9}
              connectNulls={false}
            />
          ))}
        </AreaChart>
      </ResponsiveContainer>
      <p className="mt-3 text-micro text-muted-gray">
        Gaps indicate no data (sensor offline) or a count suppressed below the
        privacy floor (fewer than 5).
      </p>
    </div>
  );
}
