"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { X } from "lucide-react";
import { ClassIcon } from "@/components/ClassIcon";
import { cn } from "@/lib/cn";
import { formatDublinUpdated } from "@/lib/format-time";
import { USUAL_RAMP, streetDirections } from "@/lib/geo";
import { USUAL_LEVELS, usualLevel, type UsualLevel } from "@/lib/typical";
import { ROAD_USER_CLASSES, classLabel, type MetricValue, type RoadUserClass, type StreetReading, type StreetSummary } from "@/lib/types";

interface Props { street: StreetSummary | null; metric: MetricValue | null; reading?: StreetReading | null; onClose: () => void; }
export const PANEL_CLASS = cn("pointer-events-auto fixed z-30 overflow-y-auto border border-line bg-surface text-ink-1 shadow-[var(--card-shadow)]", "inset-x-0 bottom-0 max-h-[75dvh] rounded-t-md", "md:left-auto md:bottom-auto md:right-0 md:top-0 md:h-full md:w-[400px] md:rounded-none md:max-h-none");
const fmt = (n: number | null | undefined) => n === null || n === undefined ? "—" : new Intl.NumberFormat("en-IE", { maximumFractionDigits: 1 }).format(n);
// Hidden values (under 5, or a direction split that would reveal one) show as
// a dash; one footnote explains them (src/lib/privacy.ts).
const HIDDEN_NOTE = "Some values under 5 are hidden.";
const V85_NOTE = "v85: the speed 85 % of road users do not exceed.";
const USUAL_SENTENCE: Record<UsualLevel, string> = {
  "much-lower": "Much quieter than usual",
  lower: "Quieter than usual",
  usual: "About usual for this time",
  higher: "Busier than usual",
  "much-higher": "Much busier than usual",
};
// A published total is the sum of the published cells beneath it.
function publishedSum(breakdown: Record<RoadUserClass, number | null>): number {
  return Object.values(breakdown).reduce<number>((sum, value) => sum + (value ?? 0), 0);
}

export function StreetSidePanel({ street, metric, reading, onClose }: Props) {
  const [fetched, setFetched] = useState<StreetReading | null>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    if (!street) return;
    headingRef.current?.focus();
    const escape = (event: KeyboardEvent) => { if (event.key === "Escape") { event.preventDefault(); onClose(); } };
    window.addEventListener("keydown", escape);
    return () => window.removeEventListener("keydown", escape);
  }, [street, onClose]);
  useEffect(() => {
    if (!street || reading !== undefined || !metric?.lastSeen) return;
    let cancelled = false;
    const to = new Date(metric.lastSeen);
    const from = new Date(to.getTime() - 15 * 60_000);
    const url = `/api/streets/${encodeURIComponent(street.id)}/readings?from=${encodeURIComponent(from.toISOString())}&to=${encodeURIComponent(to.toISOString())}&bucket=15`;
    fetch(url).then((response) => response.ok ? response.json() as Promise<StreetReading[]> : []).then((rows) => { if (!cancelled) setFetched(rows.findLast((row) => !row.missing) ?? null); }).catch(() => {});
    return () => { cancelled = true; };
  }, [street, metric?.lastSeen, reading]);
  if (!street) return null;
  const current = reading === undefined ? fetched : reading;
  const [ab, ba] = streetDirections(street);
  // Direction columns only when the sensor sends direction cells (schema 1.1).
  const split = current?.countsByDirection;
  const perClass = current ? ROAD_USER_CLASSES.filter((cls) => (current.counts[cls] ?? 0) > 0).sort((a, b) => (current.counts[b] ?? 0) - (current.counts[a] ?? 0)) : [];
  const readingHidden = current ? [current.counts, current.countsByDirection?.AB ?? {}, current.countsByDirection?.BA ?? {}].some((cells) => Object.values(cells).some((value) => value === null)) : false;
  const hasHidden = Boolean(metric?.hasHidden) || readingHidden;
  // Everything hidden: a 0 here would be a claim of no traffic, so dash it.
  const total = !metric || (hasHidden && metric.totalCount === 0) ? "—" : fmt(metric.totalCount);
  const sums = split ? [publishedSum(split.AB), publishedSum(split.BA)] : null;
  const pairHidden = split ? [split.AB, split.BA].some((cells) => Object.values(cells).some((value) => value === null)) : false;
  const showSplit = sums !== null && !(pairHidden && sums[0] === 0 && sums[1] === 0);
  const level = metric && !metric.stale ? usualLevel(metric.totalCount, metric.typical) : null;
  const status = !metric?.lastSeen ? "No data yet" : metric.stale ? `No recent data · last seen ${formatDublinUpdated(metric.lastSeen)}` : `Updated ${formatDublinUpdated(metric.lastSeen)}`;
  return <div className={PANEL_CLASS} role="dialog" aria-label={street.displayName}>
    <div className="sticky top-0 z-10 flex min-h-11 items-center justify-end border-b border-line bg-surface px-4 md:hidden"><span className="mx-auto h-1 w-9 rounded-full bg-ink-3" aria-hidden="true" /><button onClick={onClose} aria-label="Close street panel" className="flex h-11 w-11 items-center justify-center rounded-sm"><X size={20} /></button></div>
    <div className="p-4 md:p-6">
      <div className="flex items-start justify-between gap-3"><h2 ref={headingRef} tabIndex={-1} className="text-[length:var(--t-lg)] font-semibold leading-7">{street.displayName}</h2><button onClick={onClose} aria-label="Close street panel" className="hidden h-11 w-11 shrink-0 items-center justify-center rounded-sm md:flex"><X size={20} /></button></div>
      <p className="mt-2 text-sm text-ink-2">{status}</p>
      <div className="mt-5 rounded-md border border-line p-4"><p className="text-xs text-ink-2">Road users · last 15 min</p><p className="mt-1 text-[length:var(--t-xl)] font-bold tabular-nums">{total}</p>
        {showSplit && <p className="mt-2 text-sm text-ink-2">{`${ab} ${fmt(sums[0])} · ${ba} ${fmt(sums[1])}`}</p>}
        {level && <p className="mt-2 flex items-center gap-2 text-sm"><span aria-hidden="true" className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: USUAL_RAMP[USUAL_LEVELS.indexOf(level)] }} />{USUAL_SENTENCE[level]}</p>}
      </div>
      <div className="mt-5"><h3 className="mb-2 text-sm font-semibold">By class</h3>
        {perClass.length ? <div className="overflow-x-auto"><table className="w-full table-fixed text-sm"><thead><tr className="border-b border-line text-xs text-ink-2"><th className="w-[34%] py-2 text-left font-normal">Class</th><th className="text-right font-normal">Count</th>{split && <><th className="text-right font-normal">→ {ab}</th><th className="text-right font-normal">→ {ba}</th></>}<th className="text-right font-normal" title="Mean speed, km/h">km/h</th><th className="text-right font-normal" title="85th-percentile speed, km/h">v85</th></tr></thead><tbody>{perClass.map((cls) => <tr key={cls} className="border-b border-line"><th scope="row" className="py-2 text-left font-normal"><span className="mr-2 inline-block align-[-3px] text-ink-2"><ClassIcon cls={cls} /></span>{classLabel(cls)}</th><td className="text-right tabular-nums">{fmt(current?.counts[cls])}</td>{split && <><td className="text-right tabular-nums">{fmt(split.AB[cls])}</td><td className="text-right tabular-nums">{fmt(split.BA[cls])}</td></>}<td className="text-right tabular-nums text-ink-2">{fmt(current?.avgSpeedKmh[cls])}</td><td className="text-right tabular-nums text-ink-2">{fmt(current?.v85Kmh[cls])}</td></tr>)}</tbody></table></div> : <p className="text-sm text-ink-2">No published counts in this window.</p>}
        {hasHidden && <p className="mt-2 text-xs text-ink-2">{HIDDEN_NOTE}</p>}
        {perClass.some((cls) => current?.v85Kmh[cls] != null) && <p className="mt-1 text-xs text-ink-2">{V85_NOTE}</p>}
      </div>
      <div className="mt-5 flex flex-wrap gap-x-6">
        <Link href={`/${street.city}/street/${street.id}` as never} className="inline-flex min-h-11 items-center text-sm font-semibold underline underline-offset-4">Detailed view →</Link>
        <Link href={`/${street.city}/analysis?street=${encodeURIComponent(street.id)}` as never} className="inline-flex min-h-11 items-center text-sm font-semibold underline underline-offset-4">Compare roads →</Link>
      </div>
    </div>
  </div>;
}
