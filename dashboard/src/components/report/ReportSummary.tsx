import { classSummary, classesWithData } from "@/lib/class-summary";
import { formatDublinTime } from "@/lib/format-time";
import { classLabel, type StreetReading } from "@/lib/types";

// The figures behind the charts, for the printed report only: on screen the
// charts and the class view already show them.
export function ReportSummary({ readings }: { readings: StreetReading[] }) {
  const classes = classesWithData(readings);
  if (!classes.length) return null;
  return (
    <table className="mt-6 hidden w-full border-collapse text-sm print:table">
      <caption className="mb-2 text-left font-semibold">Last 24 hours by class</caption>
      <thead>
        <tr className="border-b border-[var(--line)] text-left text-[var(--ink-2)]">
          <th className="py-1 font-normal">Class</th>
          <th className="py-1 text-right font-normal">Total</th>
          <th className="py-1 text-right font-normal">Busiest 15 min</th>
          <th className="py-1 text-right font-normal">Avg speed</th>
        </tr>
      </thead>
      <tbody>
        {classes.map((cls) => {
          const s = classSummary(readings, cls);
          return (
            <tr key={cls} className="border-b border-[var(--line)]">
              <td className="py-1">{classLabel(cls)}</td>
              <td className="py-1 text-right tabular-nums">{s.total.toLocaleString("en-IE")}</td>
              <td className="py-1 text-right tabular-nums">{s.peak ? `${s.peak.count} at ${formatDublinTime(s.peak.bucket)}` : "–"}</td>
              <td className="py-1 text-right tabular-nums">{s.avgSpeedKmh === null ? "–" : `${Math.round(s.avgSpeedKmh)} km/h`}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
