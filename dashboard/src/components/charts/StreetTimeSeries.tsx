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
import { ROAD_USER_CLASSES, classLabel, type RoadUserClass, type StreetReading } from "@/lib/types";
import { formatDublinTime } from "@/lib/format-time";

interface Props {
  readings: StreetReading[];
}

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

export function StreetTimeSeries({ readings }: Props) {
  if (!readings.some((row) => !row.missing && Object.values(row.counts).some((count) => count !== null && count > 0))) {
    return (
      <div className="card flex h-64 items-center justify-center border border-[var(--line)] bg-[var(--surface)] px-6 text-center text-[var(--ink-2)]">
        No published counts in the last 24 h
      </div>
    );
  }
  const data = readings.map((r) => ({
    t: formatDublinTime(r.bucket),
    ...r.counts,
  }));

  return (
    <div className="card border border-[var(--line)] bg-[var(--surface)] p-4 sm:p-6">
      <ResponsiveContainer width="100%" height={320}>
        <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 8, left: 0 }}>
          <CartesianGrid stroke="var(--line)" vertical={false} />
          <XAxis dataKey="t" stroke="var(--ink-2)" fontSize={12} tickMargin={8} />
          <YAxis stroke="var(--ink-2)" fontSize={12} tickMargin={8} allowDecimals={false} />
          <Tooltip
            contentStyle={{
              background: "var(--surface)",
              borderRadius: 6,
              border: "1px solid var(--line)",
              color: "var(--ink-1)",
              fontSize: 12,
            }}
            labelStyle={{ color: "var(--ink-1)" }}
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          {ROAD_USER_CLASSES.map((cls: RoadUserClass, i) => (
            <Area
              key={cls}
              type="monotone"
              dataKey={cls}
              name={classLabel(cls)}
              stackId="counts"
              stroke={SERIES_COLOURS[i]}
              fill={SERIES_COLOURS[i]}
              fillOpacity={0.9}
              connectNulls={false}
            />
          ))}
        </AreaChart>
      </ResponsiveContainer>
      <p className="mt-3 text-micro text-[var(--ink-2)]">
        Gaps indicate no data (sensor offline) or a count suppressed below the
        privacy floor (fewer than 5).
      </p>
    </div>
  );
}
