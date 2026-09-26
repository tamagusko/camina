import { VIRIDIS_5 } from "@/lib/geo";
import type { Metric } from "@/lib/types";

const labels = {
  counts: ["5–24", "25–74", "75–199", "200–499", "500+"],
  speed: ["<10", "10–19", "20–29", "30–49", "50+"],
};
export function ColourLegend({ metric, compact = false }: { metric: Metric; compact?: boolean }) {
  return <div className={compact ? "text-ink-1" : "rounded-md border border-line bg-surface p-3 text-ink-1 shadow-[var(--card-shadow)]"}>
    <p className="mb-2 text-xs font-semibold">{metric === "counts" ? "Road users per 15 min" : "Speed · km/h"}</p>
    <div className="flex gap-1" aria-hidden="true">{VIRIDIS_5.map((colour, i) => <div key={colour} className="min-w-0 flex-1"><div className="h-2 rounded-sm" style={{ backgroundColor: colour }} /><span className="mt-1 block whitespace-nowrap text-xs text-ink-2">{labels[metric][i]}</span></div>)}</div>
    <dl className="sr-only">{labels[metric].map((label, i) => <div key={label}><dt>{label}</dt><dd>{VIRIDIS_5[i]}</dd></div>)}</dl>
    <div className="mt-2 flex gap-4 text-xs text-ink-2"><span>— Suppressed &lt;5</span><span>┄ No recent data</span></div>
  </div>;
}
