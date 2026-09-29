"use client";
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { TOOLTIP_STYLE } from "@/components/charts/chart-style";
import type { SpeedFigures } from "@/lib/types";

interface Props {
  byHour: SpeedFigures[];
  limit: number | null;
}

const V85_COLOUR = "var(--ink-1)";
const MEAN_COLOUR = "#0072b2"; // Okabe–Ito blue, as in the other charts
const LIMIT_COLOUR = "#d55e00"; // Okabe–Ito vermillion

/** v85 and mean speed per hour of the day, against the limit. */
export function SpeedByHourChart({ byHour, limit }: Props) {
  const data = byHour.map((h, hour) => ({
    t: `${String(hour).padStart(2, "0")}:00`,
    v85: h.v85Kmh === null ? null : Math.round(h.v85Kmh),
    mean: h.meanKmh === null ? null : Math.round(h.meanKmh),
    above: h.overLimitShare,
  }));
  const top = Math.max(limit ?? 0, ...data.map((d) => d.v85 ?? 0));
  return (
    <>
      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={data} margin={{ top: 8, right: 8, bottom: 8, left: 0 }}>
          <CartesianGrid stroke="var(--line)" vertical={false} />
          <XAxis dataKey="t" stroke="var(--ink-2)" fontSize={12} tickMargin={8} interval={5} />
          <YAxis stroke="var(--ink-2)" fontSize={12} tickMargin={8} allowDecimals={false} domain={[0, Math.ceil((top + 5) / 10) * 10]} />
          <Tooltip
            {...TOOLTIP_STYLE}
            formatter={(value, name) => [`${value} km/h`, name]}
            labelFormatter={(label, items) => {
              const above = items?.[0]?.payload?.above as number | null | undefined;
              return above == null || limit === null ? String(label) : `${label} · ${Math.round(above * 100)} % above ${limit} km/h`;
            }}
          />
          {limit !== null && (
            <ReferenceLine y={limit} stroke={LIMIT_COLOUR} strokeDasharray="6 4" ifOverflow="extendDomain" />
          )}
          <Line type="monotone" dataKey="v85" name="v85" stroke={V85_COLOUR} strokeWidth={2} dot={false} connectNulls={false} isAnimationActive={false} />
          <Line type="monotone" dataKey="mean" name="Mean" stroke={MEAN_COLOUR} strokeWidth={2} strokeDasharray="5 4" dot={false} connectNulls={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
      <p className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-micro text-[var(--ink-2)]" aria-hidden="true">
        <span><span className="mr-1 inline-block w-5 border-t-2 align-middle" style={{ borderColor: V85_COLOUR }} />v85</span>
        <span><span className="mr-1 inline-block w-5 border-t-2 border-dashed align-middle" style={{ borderColor: MEAN_COLOUR }} />Mean</span>
        {limit !== null && <span><span className="mr-1 inline-block w-5 border-t-2 border-dashed align-middle" style={{ borderColor: LIMIT_COLOUR }} />Limit, {limit} km/h</span>}
      </p>
    </>
  );
}
