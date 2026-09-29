"use client";
import { Area, AreaChart, CartesianGrid, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ClassIcon } from "@/components/ClassIcon";
import { classSummary } from "@/lib/class-summary";
import { formatDublinTime } from "@/lib/format-time";
import { classLabel, type RoadUserClass, type StreetReading } from "@/lib/types";
import { BUCKET_MS, OFFLINE_FILL, TIME_AXIS, TOOLTIP_STYLE, offlineRanges, timeLabel } from "./chart-style";

interface Props {
  cls: RoadUserClass;
  colour: string;
  readings: StreetReading[];
  directions: [string, string];
  v85?: number | null;
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-micro text-[var(--ink-2)]">{label}</dt>
      <dd className="text-lg font-semibold tabular-nums text-[var(--ink-1)]">{value}</dd>
    </div>
  );
}

/** One class on its own scale, with its totals for the window. */
export function ClassDetail({ cls, colour, readings, directions, v85 = null }: Props) {
  const s = classSummary(readings, cls);
  const label = classLabel(cls);
  const data = readings.map((r) => ({ x: Date.parse(r.bucket), [cls]: r.counts[cls] }));
  const offline = offlineRanges(readings, (r) => Date.parse(r.bucket));

  return (
    <div>
      <div className="flex items-center">
        <h2 className="flex items-center gap-2 text-base font-semibold text-[var(--ink-1)]">
          <span aria-hidden className="inline-block h-3 w-3 rounded-sm" style={{ background: colour }} />
          <ClassIcon cls={cls} size={18} />
          {label}
        </h2>
      </div>

      <dl className="mt-3 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Stat label="Total" value={s.total.toLocaleString("en-IE")} />
        <Stat
          label="Busiest 15 min"
          value={s.peak && s.peak.count > 0 ? `${s.peak.count} at ${formatDublinTime(s.peak.bucket)}` : "—"}
        />
        {s.byDirection && (
          <>
            <Stat label={`→ ${directions[0]}`} value={s.byDirection.AB.toLocaleString("en-IE")} />
            <Stat label={`→ ${directions[1]}`} value={s.byDirection.BA.toLocaleString("en-IE")} />
          </>
        )}
        <Stat label="Avg speed" value={s.avgSpeedKmh === null ? "—" : `${Math.round(s.avgSpeedKmh)} km/h`} />
        <Stat label="v85" value={v85 === null ? "—" : `${Math.round(v85)} km/h`} />
      </dl>

      <div className="mt-4">
        <ResponsiveContainer width="100%" height={280}>
          <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 8, left: 0 }}>
            <CartesianGrid stroke="var(--line)" vertical={false} />
            <XAxis {...TIME_AXIS} />
            <YAxis stroke="var(--ink-2)" fontSize={12} tickMargin={8} allowDecimals={false} />
            <Tooltip {...TOOLTIP_STYLE} labelFormatter={timeLabel} />
            {offline.map(([from, to]) => <ReferenceArea key={from} x1={from} x2={to + BUCKET_MS} fill={OFFLINE_FILL} fillOpacity={0.8} ifOverflow="hidden" />)}
            <Area
              type="monotone"
              dataKey={cls}
              name={label}
              stroke={colour}
              fill={colour}
              fillOpacity={0.35}
              strokeWidth={2}
              connectNulls={false}
              isAnimationActive={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
