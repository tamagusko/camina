"use client";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { TOOLTIP_STYLE } from "@/components/charts/chart-style";

interface Props {
  a: { label: string; profile: (number | null)[] };
  b: { label: string; profile: (number | null)[] };
}

const A_COLOUR = "var(--ink-1)";
const B_COLOUR = "#0072b2"; // Okabe–Ito blue, as in the class charts

/** Road users per hour of the day: the road solid, the comparison dashed. */
export function ProfileChart({ a, b }: Props) {
  const data = a.profile.map((value, hour) => ({
    t: `${String(hour).padStart(2, "0")}:00`,
    a: value === null ? null : Math.round(value),
    b: b.profile[hour] == null ? null : Math.round(b.profile[hour]!),
  }));
  return (
    <>
      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={data} margin={{ top: 8, right: 8, bottom: 8, left: 0 }}>
          <CartesianGrid stroke="var(--line)" vertical={false} />
          <XAxis dataKey="t" stroke="var(--ink-2)" fontSize={12} tickMargin={8} interval={5} />
          <YAxis stroke="var(--ink-2)" fontSize={12} tickMargin={8} allowDecimals={false} />
          <Tooltip {...TOOLTIP_STYLE} />
          <Line type="monotone" dataKey="a" name={a.label} stroke={A_COLOUR} strokeWidth={2} dot={false} connectNulls={false} isAnimationActive={false} />
          <Line type="monotone" dataKey="b" name={b.label} stroke={B_COLOUR} strokeWidth={2} strokeDasharray="5 4" dot={false} connectNulls={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
      <p className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-micro text-[var(--ink-2)]" aria-hidden="true">
        <span><span className="mr-1 inline-block w-5 border-t-2 align-middle" style={{ borderColor: A_COLOUR }} />{a.label}</span>
        <span><span className="mr-1 inline-block w-5 border-t-2 border-dashed align-middle" style={{ borderColor: B_COLOUR }} />{b.label}</span>
      </p>
    </>
  );
}
