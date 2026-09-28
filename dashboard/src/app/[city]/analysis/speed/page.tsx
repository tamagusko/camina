import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import { z } from "zod";
import { AnalysisTabs } from "@/components/analysis/AnalysisTabs";
import { SpeedByHourChart } from "@/components/analysis/SpeedByHourChart";
import { SpeedControls } from "@/components/analysis/SpeedControls";
import { ClassIcon } from "@/components/ClassIcon";
import { CreditFooter } from "@/components/layout/CreditFooter";
import { MockBadge, MockNotice } from "@/components/layout/MockBadge";
import { PrintFooter, ReportActions } from "@/components/report/ReportActions";
import { ANALYSIS_WINDOWS, WINDOW_LABEL } from "@/lib/analysis";
import { isMock } from "@/lib/data-source";
import { CITY_VIEWS } from "@/lib/geo";
import { streetsRepo } from "@/lib/repo";
import { classSchema } from "@/lib/schemas";
import { MOTOR_CLASSES, ROAD_USER_CLASSES, classLabel, type RoadUserClass, type SpeedFigures } from "@/lib/types";

// Speed analysis: how fast road users go on one road, and how many exceed its
// limit. The limit is the road's OpenStreetMap maxspeed unless the reader
// picks another. Every figure comes from published cells (src/lib/speed.ts).

export const metadata: Metadata = { title: "Speed · Road analysis · CAMINA" };

interface Props {
  params: Promise<{ city: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

const querySchema = z.object({
  street: z.string().optional().catch(undefined),
  window: z.enum(ANALYSIS_WINDOWS).catch("7d"),
  class: classSchema.optional().catch(undefined),
  limit: z.coerce.number().int().min(5).max(130).optional().catch(undefined),
});

const PLURAL: Record<RoadUserClass, string> = {
  person: "pedestrians", cyclist: "cyclists", car: "cars", "e-scooter": "e-scooters", SUV: "SUVs",
  motorcyclist: "motorcyclists", bus: "buses", delivery_van: "delivery vans", truck: "trucks",
};

const int = new Intl.NumberFormat("en-IE", { maximumFractionDigits: 0 });
const kmh = (v: number | null) => (v === null ? "—" : `${int.format(v)} km/h`);
const pct = (share: number | null) => (share === null ? "—" : `${Math.round(share * 100)} %`);

function Stat({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div>
      <dt className="text-micro text-[var(--ink-2)]">{label}</dt>
      <dd className="text-lg font-semibold tabular-nums text-[var(--ink-1)]">{value}</dd>
      {note && <dd className="text-micro text-[var(--ink-2)]">{note}</dd>}
    </div>
  );
}

function above(f: SpeedFigures, count: number | null): string {
  if (count === null) return "—";
  return f.timed === null ? int.format(count) : `${int.format(count)} of ${int.format(f.timed)}`;
}

function v85Note(v85: number | null, limit: number | null): string | undefined {
  if (v85 === null || limit === null) return undefined;
  const d = Math.round(v85 - limit);
  return d === 0 ? "At the limit" : `${Math.abs(d)} km/h ${d > 0 ? "above" : "below"} the limit`;
}

export default async function SpeedPage({ params, searchParams }: Props) {
  const { city } = await params;
  if (!(city in CITY_VIEWS)) notFound();
  const q = querySchema.parse(await searchParams);
  const streets = await streetsRepo.list(city);
  const street = streets.find((s) => s.id === q.street) ?? streets[0];
  if (!street) notFound();
  const focus = q.class ?? "motor";
  const limit = q.limit ?? street.speedLimitKmh;
  const bound = focus === "motor" || (MOTOR_CLASSES as readonly RoadUserClass[]).includes(focus);
  const shownLimit = bound ? limit : null;

  // The limit reaches every motor class in the table; the headline hides it
  // when the focus is not bound by it.
  const r = await streetsRepo.speeds({ streetId: street.id, window: q.window, focus, limitKmh: limit });
  const f = r.focus;
  const subject = focus === "motor" ? "motor vehicles" : PLURAL[focus];
  const limitSource = limit === null ? undefined : limit === street.speedLimitKmh ? "OpenStreetMap" : "Chosen here";
  const classes = ROAD_USER_CLASSES.filter((c) => r.byClass[c]?.timed != null);

  return (
    <main className="mx-auto w-full max-w-[960px] px-4 py-8 sm:px-6 sm:py-10">
      <div className="flex items-center gap-3">
        <Link
          href={`/${city}?street=${encodeURIComponent(street.id)}` as never}
          className="inline-flex min-h-11 items-center text-sm print:hidden font-medium text-[var(--ink-1)] underline-offset-4 hover:underline"
        >
          ← Map
        </Link>
        <span className="hidden text-xs font-semibold uppercase tracking-wide text-[var(--ink-2)] print:inline">CAMINA · Speed</span>
        {isMock && <MockBadge />}
        <ReportActions title={`${street.displayName} · Speed · CAMINA`} />
      </div>
      <h1 className="mt-4 text-[length:var(--t-xl)] font-bold leading-[34px] text-[var(--ink-1)]">Road analysis</h1>
      <AnalysisTabs city={city} street={street.id} window={q.window} active="speed" />
      <p className="mt-4 text-sm text-[var(--ink-2)] sm:text-base">
        Speeds of {subject} on {street.displayName} · {WINDOW_LABEL[q.window].toLowerCase()}
      </p>
      {isMock && <div className="mt-3"><MockNotice /></div>}

      <section className="mt-6">
        <SpeedControls
          streets={streets.map(({ id, displayName }) => ({ id, displayName }))}
          street={street.id}
          window={q.window}
          focus={focus}
          limit={limit}
          roadLimit={street.speedLimitKmh}
        />
      </section>

      <section className="card mt-6 border border-[var(--line)] bg-[var(--surface)] p-4 sm:p-6">
        <h2 className="text-base font-semibold text-[var(--ink-1)]">At a glance</h2>
        {f.timed === null ? (
          <p className="mt-3 text-sm text-[var(--ink-2)]">Fewer than 5 timed {subject} in this period.</p>
        ) : (
          <dl className="mt-3 grid grid-cols-2 gap-4 sm:grid-cols-3">
            <Stat label="Speed limit" value={kmh(shownLimit)} note={bound ? limitSource : "Does not apply"} />
            <Stat label="Timed" value={int.format(f.timed)} />
            <Stat label="Mean speed" value={kmh(f.meanKmh)} />
            <Stat label="v85" value={kmh(f.v85Kmh)} note={v85Note(f.v85Kmh, shownLimit)} />
            {shownLimit !== null && (
              <>
                <Stat label="Above the limit" value={pct(f.overLimitShare)} note={above(f, f.overLimit)} />
                <Stat label="More than 10 km/h above" value={pct(f.overBy10Share)} note={above(f, f.overBy10)} />
              </>
            )}
          </dl>
        )}
        {!bound && <p className="mt-3 text-micro text-[var(--ink-2)]">The road&apos;s limit applies to motor vehicles only.</p>}
      </section>

      <section className="card mt-6 border border-[var(--line)] bg-[var(--surface)] p-4 sm:p-6">
        <h2 className="text-base font-semibold text-[var(--ink-1)]">Through the day</h2>
        <p className="mt-1 text-sm text-[var(--ink-2)]">Speeds of {subject} per hour of the day, km/h, {WINDOW_LABEL[q.window].toLowerCase()}</p>
        <div className="mt-4"><SpeedByHourChart byHour={r.byHour} limit={shownLimit} /></div>
      </section>

      {classes.length > 0 && (
        <section className="card mt-6 border border-[var(--line)] bg-[var(--surface)] p-4 sm:p-6">
          <h2 className="text-base font-semibold text-[var(--ink-1)]">By class</h2>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full table-fixed text-xs sm:text-sm">
              <thead>
                <tr className="border-b border-[var(--line)] text-xs text-[var(--ink-2)]">
                  <th className="w-[32%] py-2 text-left font-normal">Class</th>
                  <th className="py-2 text-right font-normal">Timed</th>
                  <th className="py-2 text-right font-normal">Mean</th>
                  <th className="py-2 text-right font-normal">v85</th>
                  <th className="py-2 text-right font-normal">{limit === null ? "Above limit" : `Above ${limit}`}</th>
                </tr>
              </thead>
              <tbody>
                {classes.map((c) => {
                  const row = r.byClass[c]!;
                  const motor = (MOTOR_CLASSES as readonly RoadUserClass[]).includes(c);
                  return (
                    <tr key={c} className="border-b border-[var(--line)]">
                      <th scope="row" className="py-2 text-left font-normal">
                        <span className="mr-2 inline-block align-[-3px] text-[var(--ink-2)]"><ClassIcon cls={c} /></span>{classLabel(c)}
                      </th>
                      <td className="py-2 text-right tabular-nums">{row.timed === null ? "—" : int.format(row.timed)}</td>
                      <td className="py-2 text-right tabular-nums">{row.meanKmh === null ? "—" : int.format(row.meanKmh)}</td>
                      <td className="py-2 text-right tabular-nums">{row.v85Kmh === null ? "—" : int.format(row.v85Kmh)}</td>
                      <td className="py-2 text-right tabular-nums text-[var(--ink-2)]">{motor ? pct(row.overLimitShare) : ""}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-micro text-[var(--ink-2)]">Speeds in km/h. The limit is not shown for road users it does not bind.</p>
        </section>
      )}

      <div className="mt-4 space-y-1 text-micro text-[var(--ink-2)]">
        <p>v85: the speed that 85 % of timed road users do not exceed. Speed limit: the road&apos;s OpenStreetMap maxspeed unless another is chosen.</p>
        <p>Only road users timed between the sensor&apos;s two speed lines count. Figures over fewer than 5 are hidden, and so is a count above the limit when it, or the count below, is 1 to 4.</p>
      </div>

      <Link href={`/${city}/street/${street.id}` as never} className="mt-5 inline-flex min-h-11 items-center text-sm font-semibold underline underline-offset-4 print:hidden">
        Detailed view of {street.displayName} →
      </Link>
      <PrintFooter />
      <CreditFooter />
    </main>
  );
}
