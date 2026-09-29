"use client";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { TOOLTIP_STYLE } from "@/components/charts/chart-style";

/** One hour of the day, average timed road users per day the sensor was up. */
export interface HourCounts {
  below: number | null;
  above: number | null;
  unsplit: number | null; // the split is hidden: only the total is shown
}

interface Props {
  byHour: HourCounts[];
  limit: number;
}

const ABOVE_COLOUR = "#d55e00"; // Okabe–Ito vermillion, the limit's colour
const BELOW_COLOUR = "var(--ink-3)";
const UNSPLIT_COLOUR = "var(--line)";

const perDay = (n: number) => (n < 10 ? n.toFixed(1) : String(Math.round(n)));

/** Road users above and below the limit per hour of the day, stacked. */
export function SpeedCountsByHourChart({ byHour, limit }: Props) {
  const data = byHour.map((h, hour) => ({ t: `${String(hour).padStart(2, "0")}:00`, ...h }));
  const bar = { stackId: "h", isAnimationActive: false, stroke: "var(--surface)", strokeWidth: 1 };
  return (
    <>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data} margin={{ top: 8, right: 8, bottom: 8, left: 0 }} barCategoryGap={2}>
          <CartesianGrid stroke="var(--line)" vertical={false} />
          <XAxis dataKey="t" stroke="var(--ink-2)" fontSize={12} tickMargin={8} interval={5} />
          <YAxis stroke="var(--ink-2)" fontSize={12} tickMargin={8} allowDecimals={false} />
          <Tooltip
            {...TOOLTIP_STYLE}
            cursor={{ fill: "var(--line)", opacity: 0.4 }}
            formatter={(value, name) => [`${perDay(Number(value))} a day`, name]}
          />
          <Bar dataKey="below" name={`At or below ${limit} km/h`} fill={BELOW_COLOUR} {...bar} />
          <Bar dataKey="above" name={`Above ${limit} km/h`} fill={ABOVE_COLOUR} radius={[3, 3, 0, 0]} {...bar} />
          <Bar dataKey="unsplit" name="Split hidden" fill={UNSPLIT_COLOUR} radius={[3, 3, 0, 0]} {...bar} />
        </BarChart>
      </ResponsiveContainer>
      <p className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-micro text-[var(--ink-2)]" aria-hidden="true">
        <span><span className="mr-1 inline-block size-2.5 rounded-sm align-middle" style={{ background: BELOW_COLOUR }} />At or below {limit} km/h</span>
        <span><span className="mr-1 inline-block size-2.5 rounded-sm align-middle" style={{ background: ABOVE_COLOUR }} />Above {limit} km/h</span>
        {data.some((d) => d.unsplit !== null) && (
          <span><span className="mr-1 inline-block size-2.5 rounded-sm align-middle" style={{ background: UNSPLIT_COLOUR }} />Split hidden</span>
        )}
      </p>
    </>
  );
}
