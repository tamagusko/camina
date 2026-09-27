"use client";
import { useState } from "react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { classesWithData } from "@/lib/class-summary";
import { classLabel, type RoadUserClass, type StreetReading } from "@/lib/types";
import { formatDublinTime } from "@/lib/format-time";
import { cn } from "@/lib/cn";
import { CLASS_COLOURS, TOOLTIP_STYLE } from "./chart-style";
import { ClassDetail } from "./ClassDetail";

interface Props {
  readings: StreetReading[];
  directions?: [string, string];
}

export function StreetTimeSeries({ readings, directions = ["A", "B"] }: Props) {
  const [selected, setSelected] = useState<RoadUserClass | null>(null);
  const classes = classesWithData(readings);
  if (!classes.length) {
    return (
      <div className="card flex h-64 items-center justify-center border border-[var(--line)] bg-[var(--surface)] px-6 text-center text-[var(--ink-2)]">
        No published counts in the last 24 h
      </div>
    );
  }
  const toggle = (cls: RoadUserClass) => setSelected((cur) => (cur === cls ? null : cls));
  const data = readings.map((r) => ({
    t: formatDublinTime(r.bucket),
    ...r.counts,
  }));

  return (
    <div className="card border border-[var(--line)] bg-[var(--surface)] p-4 sm:p-6">
      {selected ? (
        <ClassDetail
          cls={selected}
          colour={CLASS_COLOURS[selected]}
          readings={readings}
          directions={directions}
          onBack={() => setSelected(null)}
        />
      ) : (
        <ResponsiveContainer width="100%" height={320}>
          <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 8, left: 0 }}>
            <CartesianGrid stroke="var(--line)" vertical={false} />
            <XAxis dataKey="t" stroke="var(--ink-2)" fontSize={12} tickMargin={8} />
            <YAxis stroke="var(--ink-2)" fontSize={12} tickMargin={8} allowDecimals={false} />
            <Tooltip {...TOOLTIP_STYLE} />
            {classes.map((cls) => (
              <Area
                key={cls}
                type="monotone"
                dataKey={cls}
                name={classLabel(cls)}
                stackId="counts"
                stroke={CLASS_COLOURS[cls]}
                fill={CLASS_COLOURS[cls]}
                fillOpacity={0.9}
                connectNulls={false}
                onClick={() => setSelected(cls)}
                style={{ cursor: "pointer" }}
              />
            ))}
          </AreaChart>
        </ResponsiveContainer>
      )}

      <ul className="mt-4 flex flex-wrap gap-2" aria-label="Classes">
        {classes.map((cls) => (
          <li key={cls}>
            <button
              type="button"
              aria-pressed={selected === cls}
              onClick={() => toggle(cls)}
              className={cn(
                "inline-flex min-h-9 items-center gap-2 rounded-full border px-3 text-xs text-[var(--ink-1)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--focus)]",
                selected === cls ? "border-[var(--ink-1)] font-semibold" : "border-[var(--line)] hover:border-[var(--ink-2)]",
                selected && selected !== cls && "opacity-60",
              )}
            >
              <span aria-hidden className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: CLASS_COLOURS[cls] }} />
              {classLabel(cls)}
            </button>
          </li>
        ))}
      </ul>

      <p className="mt-3 text-micro text-[var(--ink-2)]">
        {selected ? null : "Select a class, in the chart or above, to see it on its own. "}
        Gaps mean no data (sensor offline) or a count under 5, which is hidden
        and left out of totals and averages.
      </p>
    </div>
  );
}
