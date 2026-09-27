import { VIRIDIS_5 } from "@/lib/geo";
import type { Metric, TimeWindow } from "@/lib/types";

const labels = {
  counts: ["5–24", "25–74", "75–199", "200–499", "500+"],
  speed: ["<10", "10–19", "20–29", "30–49", "50+"],
};
// Counts under 5 (none, or hidden) paint the quiet grey (rampExpression).
const QUIET = "var(--ink-3)";
const keys: Record<Metric, [string, string][]> = {
  counts: [[QUIET, "<5"], ...VIRIDIS_5.map((colour, i): [string, string] => [colour, labels.counts[i]!])],
  speed: VIRIDIS_5.map((colour, i): [string, string] => [colour, labels.speed[i]!]),
};
const WINDOW_LABEL: Record<TimeWindow, string> = { now: "", "1h": " · 1 h average", "24h": " · 24 h average", "7d": " · 7 d average", "30d": " · 30 d average" };
export function ColourLegend({ metric, timeWindow = "now", compact = false }: { metric: Metric; timeWindow?: TimeWindow; compact?: boolean }) {
  return <div className={compact ? "text-ink-1" : "rounded-md border border-line bg-surface p-3 text-ink-1 shadow-[var(--card-shadow)]"}>
    <p className={compact ? "mb-1 text-xs font-semibold" : "mb-2 text-xs font-semibold"}>{metric === "counts" ? `Road users per 15 min${WINDOW_LABEL[timeWindow]}` : "Speed · km/h"}</p>
    <div className="flex gap-1" aria-hidden="true">{keys[metric].map(([colour, label]) => <div key={label} className="min-w-0 flex-1"><div className="h-2 rounded-sm" style={{ backgroundColor: colour }} /><span className="mt-1 block whitespace-nowrap text-xs text-ink-2">{label}</span></div>)}</div>
    <dl className="sr-only">{keys[metric].map(([colour, label]) => <div key={label}><dt>{label}</dt><dd>{colour === QUIET ? "grey" : colour}</dd></div>)}</dl>
    {!compact && <div className="mt-2 flex gap-4 text-xs text-ink-2"><span>— Suppressed &lt;5</span><span>┄ No recent data</span></div>}
  </div>;
}
