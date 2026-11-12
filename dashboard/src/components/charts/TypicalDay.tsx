"use client";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { typicalDay } from "@/lib/typical-day";
import { classLabel, type RoadUserClass, type StreetReading } from "@/lib/types";
import { TOOLTIP_STYLE } from "./chart-style";

interface Props {
  readings: StreetReading[];
  cls: RoadUserClass | null;
  colour: string;
  weeks: number;
}

/** Average road users per hour: weekdays solid, weekends dashed. */
export function TypicalDay({ readings, cls, colour, weeks }: Props) {
  const day = typicalDay(readings, cls).map((h) => ({
    t: `${String(h.hour).padStart(2, "0")}:00`,
    Weekdays: h.weekday === null ? null : Math.round(h.weekday),
    Weekends: h.weekend === null ? null : Math.round(h.weekend),
  }));
  if (!day.some((h) => h.Weekdays !== null || h.Weekends !== null)) return null;

  return (
    <section className="card mt-6 border border-[var(--line)] bg-[var(--surface)] p-4 sm:p-6">
      <h2 className="text-base font-semibold text-[var(--ink-1)]">
        A typical day{cls ? ` · ${classLabel(cls)}` : ""}
      </h2>
      <p className="mt-1 text-sm text-[var(--ink-2)]">Average per hour over the last {weeks} weeks</p>
      <div className="mt-4">
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={day} margin={{ top: 8, right: 8, bottom: 8, left: 0 }}>
            <CartesianGrid stroke="var(--line)" vertical={false} />
            <XAxis dataKey="t" stroke="var(--ink-2)" fontSize={12} tickMargin={8} interval={5} />
            <YAxis stroke="var(--ink-2)" fontSize={12} tickMargin={8} allowDecimals={false} />
            <Tooltip {...TOOLTIP_STYLE} />
            <Line type="monotone" dataKey="Weekdays" stroke={colour} strokeWidth={2} dot={false} connectNulls={false} isAnimationActive={false} />
            <Line type="monotone" dataKey="Weekends" stroke={colour} strokeWidth={2} strokeDasharray="5 4" dot={false} connectNulls={false} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-2 flex gap-4 text-micro text-[var(--ink-2)]" aria-hidden="true">
        <span><span className="mr-1 inline-block w-5 border-t-2 align-middle" style={{ borderColor: colour }} />Weekdays</span>
        <span><span className="mr-1 inline-block w-5 border-t-2 border-dashed align-middle" style={{ borderColor: colour }} />Weekends</span>
      </p>
    </section>
  );
}
