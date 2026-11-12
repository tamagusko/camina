import type { SpeedFigures } from "@/lib/types";

interface Props {
  week: SpeedFigures[][]; // 7 weekdays (Monday first) × 24 hours
  limit: number;
}

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const HUE = "#d55e00"; // Okabe–Ito vermillion, the limit's colour

/** Share above the limit by weekday and hour: one hue, light to dark. A table,
 *  so every value is also text. Blank cells: too few road users, or hidden. */
export function SpeedWeekHeatmap({ week, limit }: Props) {
  const shares = week.flat().map((f) => f.overLimitShare).filter((s): s is number => s !== null);
  // The ramp ends at the highest share, in steps of 10 %, so the page's own
  // spread is visible whether a road is mostly under the limit or not.
  const top = Math.max(0.1, Math.ceil(Math.max(0, ...shares) * 10) / 10);
  const tone = (share: number) => Math.round(8 + (share / top) * 82); // % of the hue over the surface
  const hh = (h: number) => String(h).padStart(2, "0");
  return (
    <>
      <div className="mx-auto max-w-[420px]">
        <table className="w-full table-fixed border-separate border-spacing-[2px] text-micro tabular-nums">
          <caption className="sr-only">Share of timed road users above {limit} km/h, by weekday and hour of the day</caption>
          <thead>
            <tr className="text-[var(--ink-2)]">
              <th className="w-9 font-normal"><span className="sr-only">Hour</span></th>
              {DAYS.map((d, i) => <th key={d} scope="col" className="pb-1 font-normal"><abbr title={DAY_NAMES[i]} className="no-underline">{d}</abbr></th>)}
            </tr>
          </thead>
          <tbody>
            {Array.from({ length: 24 }, (_, hour) => (
              <tr key={hour}>
                <th scope="row" className="pr-1 text-right font-normal text-[var(--ink-2)]">{hour % 3 === 0 ? `${hh(hour)}:00` : <span className="sr-only">{hh(hour)}:00</span>}</th>
                {week.map((day, dow) => {
                  const share = day[hour]?.overLimitShare ?? null;
                  const label = `${DAY_NAMES[dow]} ${hh(hour)}:00–${hh((hour + 1) % 24)}:00`;
                  if (share === null) {
                    return <td key={dow} title={`${label}: not shown`} className="h-5 rounded-[3px] border border-dashed border-[var(--line)]"><span className="sr-only">not shown</span></td>;
                  }
                  const t = tone(share);
                  const pct = Math.round(share * 100);
                  return (
                    <td
                      key={dow}
                      title={`${label}: ${pct} % above ${limit} km/h`}
                      className="h-5 rounded-[3px] text-center"
                      style={{ background: `color-mix(in oklab, ${HUE} ${t}%, var(--surface))`, color: t > 55 ? "#fff" : "var(--ink-1)" }}
                    >
                      {pct}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mx-auto mt-3 flex max-w-[420px] items-center gap-2 text-micro text-[var(--ink-2)]" aria-hidden="true">
        <span>0 %</span>
        <span className="h-2 flex-1 rounded-sm" style={{ background: `linear-gradient(to right, color-mix(in oklab, ${HUE} 8%, var(--surface)), color-mix(in oklab, ${HUE} 90%, var(--surface)))` }} />
        <span>{Math.round(top * 100)} %</span>
        <span className="ml-2 inline-block h-3 w-4 rounded-[3px] border border-dashed border-[var(--line)]" />
        <span>Not shown</span>
      </div>
    </>
  );
}
