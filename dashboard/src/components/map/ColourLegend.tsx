import { USUAL_RAMP, VIRIDIS_5, type MapMode } from "@/lib/geo";
import { TYPICAL_WEEKS } from "@/lib/typical";
import type { TimeWindow } from "@/lib/types";

const labels = {
  counts: ["5–24", "25–74", "75–199", "200–499", "500+"],
  speed: ["<10", "10–19", "20–29", "30–49", "50+"],
};
// Counts under 5 (none, or hidden) paint the quiet grey (rampExpression).
const QUIET = "var(--ink-3)";
const keys: Record<Exclude<MapMode, "usual">, [string, string][]> = {
  counts: [[QUIET, "<5"], ...VIRIDIS_5.map((colour, i): [string, string] => [colour, labels.counts[i]!])],
  speed: VIRIDIS_5.map((colour, i): [string, string] => [colour, labels.speed[i]!]),
};
const WINDOW_LABEL: Record<TimeWindow, string> = { now: "", "1h": " · 1 h average", "24h": " · 24 h average", "7d": " · 7 d average", "30d": " · 30 d average" };
const HIDDEN_NOTE = "Values under 5 are hidden and left out of totals and averages.";

function UsualKey({ compact }: { compact: boolean }) {
  return <>
    <div className="flex gap-1" aria-hidden="true">{USUAL_RAMP.map((colour) => <div key={colour} className="h-2 min-w-0 flex-1 rounded-sm" style={{ backgroundColor: colour }} />)}</div>
    <div className="mt-1 flex justify-between text-xs text-ink-2" aria-hidden="true"><span>Much quieter</span><span>Usual</span><span>Much busier</span></div>
    <p className="sr-only">From much quieter (blue) through usual (grey) to much busier (red).</p>
    <p className={compact ? "mt-1 text-[11px] leading-tight text-ink-2" : "mt-2 text-xs text-ink-2"}>
      <span className="mr-1 inline-block h-2 w-3 rounded-sm align-middle" style={{ backgroundColor: QUIET }} aria-hidden="true" />Too little data to compare
    </p>
  </>;
}

export function ColourLegend({ mode, timeWindow = "now", compact = false }: { mode: MapMode; timeWindow?: TimeWindow; compact?: boolean }) {
  const title = mode === "usual" ? "Counts vs usual" : mode === "counts" ? `Road users per 15 min${WINDOW_LABEL[timeWindow]}` : "Speed · km/h";
  const note = mode === "usual" ? `Against the same time and weekday in the past ${TYPICAL_WEEKS} weeks.` : HIDDEN_NOTE;
  return <div className={compact ? "text-ink-1" : "rounded-md border border-line bg-surface p-3 text-ink-1 shadow-[var(--card-shadow)]"}>
    <p className={compact ? "mb-1 text-xs font-semibold" : "mb-2 text-xs font-semibold"}>{title}</p>
    {mode === "usual" ? <UsualKey compact={compact} /> : <>
      <div className="flex gap-1" aria-hidden="true">{keys[mode].map(([colour, label]) => <div key={label} className="min-w-0 flex-1"><div className="h-2 rounded-sm" style={{ backgroundColor: colour }} /><span className="mt-1 block whitespace-nowrap text-xs text-ink-2">{label}</span></div>)}</div>
      <dl className="sr-only">{keys[mode].map(([colour, label]) => <div key={label}><dt>{label}</dt><dd>{colour === QUIET ? "grey" : colour}</dd></div>)}</dl>
    </>}
    <p className={compact ? "mt-1 text-[11px] leading-tight text-ink-2" : "mt-2 text-xs text-ink-2"}>{note}</p>
    {!compact && <p className="mt-1 text-xs text-ink-2">┄ No recent data</p>}
  </div>;
}
