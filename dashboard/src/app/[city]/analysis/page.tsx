import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import { z } from "zod";
import { AnalysisControls } from "@/components/analysis/AnalysisControls";
import { AnalysisTabs } from "@/components/analysis/AnalysisTabs";
import { ProfileChart } from "@/components/analysis/ProfileChart";
import { ClassIcon } from "@/components/ClassIcon";
import { CreditFooter } from "@/components/layout/CreditFooter";
import { MockBadge, MockNotice } from "@/components/layout/MockBadge";
import { PrintFooter, ReportActions } from "@/components/report/ReportActions";
import {
  ANALYSIS_WINDOWS,
  WINDOW_HOURS,
  WINDOW_LABEL,
  busiestHour,
  citySide,
  difference,
  hasData,
  hourlyProfile,
  roadSide,
  type Side,
} from "@/lib/analysis";
import { isMock } from "@/lib/data-source";
import { CITY_VIEWS } from "@/lib/geo";
import { streetsRepo } from "@/lib/repo";
import { classSchema } from "@/lib/schemas";
import { ROAD_USER_CLASSES, classLabel } from "@/lib/types";

// Road analysis: the room for analyses beyond one street's page. The first
// one compares a road with another road or with the city average.

export const metadata: Metadata = { title: "Road analysis · CAMINA" };

interface Props {
  params: Promise<{ city: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

const querySchema = z.object({
  street: z.string().optional().catch(undefined),
  vs: z.string().optional().catch(undefined),
  window: z.enum(ANALYSIS_WINDOWS).catch("7d"),
  class: classSchema.optional().catch(undefined),
});

const int = new Intl.NumberFormat("en-IE", { maximumFractionDigits: 0 });
const one = new Intl.NumberFormat("en-IE", { maximumFractionDigits: 1 });
const dash = (value: number | null, format: (v: number) => string) => (value === null ? "—" : format(value));
const kmh = (v: number) => `${int.format(v)} km/h`;
const hourRange = (h: number) => `${String(h).padStart(2, "0")}:00–${String((h + 1) % 24).padStart(2, "0")}:00`;
function signed(fraction: number | null): string {
  if (fraction === null) return "—";
  const pct = Math.round(fraction * 100);
  return pct === 0 ? "±0 %" : `${pct > 0 ? "+" : "−"}${Math.abs(pct)} %`;
}

const TH = "py-2 text-right font-normal";
const TD = "py-2 text-right tabular-nums";

export default async function AnalysisPage({ params, searchParams }: Props) {
  const { city } = await params;
  if (!(city in CITY_VIEWS)) notFound();
  const q = querySchema.parse(await searchParams);
  const streets = await streetsRepo.list(city);
  const street = streets.find((s) => s.id === q.street) ?? streets[0];
  if (!street) notFound();
  const other = q.vs && q.vs !== "city" ? streets.find((s) => s.id === q.vs && s.id !== street.id) : undefined;
  const cls = q.class ?? null;
  const hours = WINDOW_HOURS[q.window];

  const to = await streetsRepo.now();
  const from = new Date(to.getTime() - hours * 60 * 60_000);
  const classes = cls ? [cls] : undefined;
  const metrics = await streetsRepo.latestMetrics({ city, metric: "counts", window: q.window, classes });
  const byId = new Map(metrics.map((m) => [m.streetId, m]));
  // Hourly readings of every road with data: the city profile needs them all.
  const withData = streets.filter((s) => byId.get(s.id) && hasData(byId.get(s.id)!));
  const needed = other ? [street, other] : [street, ...withData.filter((s) => s.id !== street.id)];
  const readings = new Map(await Promise.all(
    needed.map(async (s) => [s.id, await streetsRepo.readings({ streetId: s.id, classes, from, to, bucketMinutes: 60 })] as const),
  ));

  const a = roadSide(street.displayName, byId.get(street.id), cls, readings.get(street.id) ?? [], hours);
  const b: Side = other
    ? roadSide(other.displayName, byId.get(other.id), cls, readings.get(other.id) ?? [], hours)
    : citySide("City average", withData.map((s) => byId.get(s.id)!), cls, withData.map((s) => hourlyProfile(readings.get(s.id) ?? [], cls)), hours);
  const busiest = [busiestHour(a.profile), busiestHour(b.profile)];

  const rows: { label: string; a: string; b: string; diff: string }[] = [
    { label: "Road users", a: dash(a.total, (v) => int.format(v)), b: dash(b.total, (v) => int.format(v)), diff: signed(difference(a.total, b.total)) },
    { label: "Per hour", a: dash(a.perHour, (v) => one.format(v)), b: dash(b.perHour, (v) => one.format(v)), diff: signed(difference(a.perHour, b.perHour)) },
    { label: "Busiest hour", a: dash(busiest[0]!, hourRange), b: dash(busiest[1]!, hourRange), diff: "" },
  ];
  if (cls) {
    rows.push(
      { label: "Mean speed", a: dash(a.meanSpeed, kmh), b: dash(b.meanSpeed, kmh), diff: signed(difference(a.meanSpeed, b.meanSpeed)) },
      { label: "v85", a: dash(a.v85, kmh), b: dash(b.v85, kmh), diff: signed(difference(a.v85, b.v85)) },
    );
  }
  const shownClasses = ROAD_USER_CLASSES.filter((c) => (a.byClass[c] ?? 0) > 0 || (b.byClass[c] ?? 0) > 0);
  const subject = cls ? classLabel(cls).toLowerCase() : "road users";

  return (
    <main className="mx-auto w-full max-w-[960px] px-4 py-8 sm:px-6 sm:py-10">
      <div className="flex items-center gap-3">
        <Link
          href={`/${city}?street=${encodeURIComponent(street.id)}` as never}
          className="inline-flex min-h-11 items-center text-sm print:hidden font-medium text-[var(--ink-1)] underline-offset-4 hover:underline"
        >
          ← Map
        </Link>
        <span className="hidden text-xs font-semibold uppercase tracking-wide text-[var(--ink-2)] print:inline">CAMINA · Road analysis</span>
        {isMock && <MockBadge />}
        <ReportActions title={`${street.displayName} · Road analysis · CAMINA`} />
      </div>
      <h1 className="mt-4 text-[length:var(--t-xl)] font-bold leading-[34px] text-[var(--ink-1)]">Road analysis</h1>
      <AnalysisTabs city={city} street={street.id} window={q.window} active="compare" />
      <p className="mt-4 text-sm text-[var(--ink-2)] sm:text-base">
        {street.displayName} compared with {other ? other.displayName : "the city average"} · {WINDOW_LABEL[q.window].toLowerCase()} · {subject}
      </p>
      {isMock && <div className="mt-3"><MockNotice /></div>}

      <section className="mt-6">
        <AnalysisControls streets={streets.map(({ id, displayName }) => ({ id, displayName }))} street={street.id} vs={other?.id ?? "city"} window={q.window} cls={cls} />
      </section>

      <section className="card mt-6 border border-[var(--line)] bg-[var(--surface)] p-4 sm:p-6">
        <h2 className="text-base font-semibold text-[var(--ink-1)]">At a glance</h2>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full table-fixed text-xs sm:text-sm">
            <thead>
              <tr className="border-b border-[var(--line)] text-xs text-[var(--ink-2)]">
                <th className="w-[24%] py-2 text-left font-normal"><span className="sr-only">Measure</span></th>
                <th className={TH} title={a.label}>This road</th>
                <th className={TH} title={b.label}>{other ? "Other road" : "City average"}</th>
                <th className={`${TH} w-[20%]`}>Diff.</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.label} className="border-b border-[var(--line)]">
                  <th scope="row" className="py-2 text-left font-normal">{row.label}</th>
                  <td className={`${TD} font-semibold`}>{row.a}</td>
                  <td className={TD}>{row.b}</td>
                  <td className={`${TD} text-[var(--ink-2)]`}>{row.diff}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!cls && <p className="mt-2 text-micro text-[var(--ink-2)] print:hidden">Choose a road-user class to compare speeds.</p>}
      </section>

      {!cls && shownClasses.length > 0 && (
        <section className="card mt-6 border border-[var(--line)] bg-[var(--surface)] p-4 sm:p-6">
          <h2 className="text-base font-semibold text-[var(--ink-1)]">By class</h2>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full table-fixed text-xs sm:text-sm">
              <thead>
                <tr className="text-xs text-[var(--ink-2)]">
                  <th className="w-[32%]" />
                  <th colSpan={2} className="py-1 text-right font-normal">Road users</th>
                  <th colSpan={2} className="py-1 text-right font-normal">v85, km/h</th>
                </tr>
                <tr className="border-b border-[var(--line)] text-xs text-[var(--ink-2)]">
                  <th className="py-2 text-left font-normal">Class</th>
                  <th className={TH} title={a.label}>This road</th>
                  <th className={TH} title={b.label}>{other ? "Other road" : "City"}</th>
                  <th className={TH} title={a.label}>This road</th>
                  <th className={TH} title={b.label}>{other ? "Other road" : "City"}</th>
                </tr>
              </thead>
              <tbody>
                {shownClasses.map((c) => (
                  <tr key={c} className="border-b border-[var(--line)]">
                    <th scope="row" className="py-2 text-left font-normal">
                      <span className="mr-2 inline-block align-[-3px] text-[var(--ink-2)]"><ClassIcon cls={c} /></span>{classLabel(c)}
                    </th>
                    <td className={TD}>{dash(a.byClass[c], (v) => int.format(v))}</td>
                    <td className={`${TD} text-[var(--ink-2)]`}>{dash(b.byClass[c], (v) => int.format(v))}</td>
                    <td className={TD}>{dash(a.v85ByClass[c] ?? null, (v) => int.format(v))}</td>
                    <td className={`${TD} text-[var(--ink-2)]`}>{dash(b.v85ByClass[c] ?? null, (v) => int.format(v))}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <section className="card mt-6 border border-[var(--line)] bg-[var(--surface)] p-4 sm:p-6">
        <h2 className="text-base font-semibold text-[var(--ink-1)]">A typical day</h2>
        <p className="mt-1 text-sm text-[var(--ink-2)]">Average {subject} per hour, {WINDOW_LABEL[q.window].toLowerCase()}</p>
        <div className="mt-4"><ProfileChart a={a} b={b} /></div>
      </section>

      <div className="mt-4 space-y-1 text-micro text-[var(--ink-2)]">
        {!other && <p>City average: the mean over the {withData.length} roads with data in this period.</p>}
        <p>v85: the speed that 85 % of timed road users do not exceed. Values under 5 are hidden and left out of totals and averages.</p>
      </div>

      <Link href={`/${city}/street/${street.id}` as never} className="mt-5 inline-flex min-h-11 items-center text-sm font-semibold underline underline-offset-4 print:hidden">
        Detailed view of {street.displayName} →
      </Link>
      <PrintFooter />
      <CreditFooter />
    </main>
  );
}
