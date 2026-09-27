"use client";
import { useState } from "react";
import { Area, AreaChart, CartesianGrid, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ClassIcon } from "@/components/ClassIcon";
import { classesWithData } from "@/lib/class-summary";
import { classLabel, type RoadUserClass, type StreetReading } from "@/lib/types";
import { cn } from "@/lib/cn";
import { BUCKET_MS, CLASS_COLOURS, OFFLINE_FILL, TIME_AXIS, TOOLTIP_STYLE, offlineRanges, timeLabel } from "./chart-style";
import { ClassDetail } from "./ClassDetail";
import { TypicalDay } from "./TypicalDay";

interface Props {
  readings: StreetReading[];
  directions?: [string, string];
  /** Hourly readings over the last `historyWeeks` weeks, for "A typical day". */
  history?: StreetReading[];
  historyWeeks?: number;
}

export function StreetTimeSeries({ readings, directions = ["A", "B"], history = [], historyWeeks = 4 }: Props) {
  const [selected, setSelected] = useState<RoadUserClass | null>(null);
  const classes = classesWithData(readings);
  const typical = (
    <TypicalDay
      readings={history}
      cls={selected}
      colour={selected ? CLASS_COLOURS[selected] : "var(--ink-1)"}
      weeks={historyWeeks}
    />
  );
  if (!classes.length) {
    return (
      <>
        <div className="card flex h-64 items-center justify-center border border-[var(--line)] bg-[var(--surface)] px-6 text-center text-[var(--ink-2)]">
          No published counts in the last 24 h
        </div>
        {typical}
      </>
    );
  }
  const data = readings.map((r) => ({ x: Date.parse(r.bucket), ...r.counts }));
  const offline = offlineRanges(readings, (r) => Date.parse(r.bucket));

  return (
    <>
      <div className="card border border-[var(--line)] bg-[var(--surface)] p-4 sm:p-6">
        {selected ? (
          <ClassDetail
            cls={selected}
            colour={CLASS_COLOURS[selected]}
            readings={readings}
            directions={directions}
          />
        ) : (
          <ResponsiveContainer width="100%" height={320}>
            <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 8, left: 0 }}>
              <CartesianGrid stroke="var(--line)" vertical={false} />
              <XAxis {...TIME_AXIS} />
              <YAxis stroke="var(--ink-2)" fontSize={12} tickMargin={8} allowDecimals={false} />
              <Tooltip {...TOOLTIP_STYLE} labelFormatter={timeLabel} />
              {offline.map(([from, to]) => (
                <ReferenceArea key={from} x1={from} x2={to + BUCKET_MS} fill={OFFLINE_FILL} fillOpacity={0.8} ifOverflow="hidden" />
              ))}
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
                  isAnimationActive={false}
                  onClick={() => setSelected(cls)}
                  style={{ cursor: "pointer" }}
                />
              ))}
            </AreaChart>
          </ResponsiveContainer>
        )}

        <ul className="mt-4 flex flex-wrap gap-2" aria-label="Classes">
          <li>
            <button type="button" aria-pressed={selected === null} onClick={() => setSelected(null)} className={chip(selected === null)}>All</button>
          </li>
          {classes.map((cls) => (
            <li key={cls}>
              <button type="button" aria-pressed={selected === cls} onClick={() => setSelected(cls)} className={chip(selected === cls)}>
                <span aria-hidden className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: CLASS_COLOURS[cls] }} />
                <ClassIcon cls={cls} size={14} />
                {classLabel(cls)}
              </button>
            </li>
          ))}
        </ul>

        <p className="mt-3 text-micro text-[var(--ink-2)]">
          {selected ? null : <span className="print:hidden">Select a class to see it on its own. </span>}
          {offline.length ? "Grey bands: sensor offline. " : null}
          Values under 5 are hidden and left out of totals and averages.
        </p>
      </div>
      {typical}
    </>
  );
}

// One look for every chip; the selected one is outlined and bold.
function chip(active: boolean): string {
  return cn(
    "inline-flex min-h-11 items-center gap-1.5 rounded-full sm:min-h-9 border px-3 text-xs text-[var(--ink-1)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--focus)]",
    active ? "border-[var(--ink-1)] font-semibold" : "border-[var(--line)] hover:border-[var(--ink-2)]",
  );
}
