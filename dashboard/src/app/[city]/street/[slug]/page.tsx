import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import { CreditFooter } from "@/components/layout/CreditFooter";
import { MockBadge, MockNotice } from "@/components/layout/MockBadge";
import { StreetTimeSeries } from "@/components/charts/StreetTimeSeries";
import { PrintFooter, ReportActions } from "@/components/report/ReportActions";
import { ReportSummary } from "@/components/report/ReportSummary";
import { streetsRepo } from "@/lib/repo";
import { isMock } from "@/lib/data-source";
import { formatDublinDateTime } from "@/lib/format-time";
import { streetDirections } from "@/lib/geo";
import { dataUpdatedAt } from "@/lib/report";

// "A typical day" averages the last four weeks.
const HISTORY_WEEKS = 4;
const WEEK_MS = 7 * 24 * 60 * 60_000;

interface Props {
  params: Promise<{ city: string; slug: string }>;
}

// The tab title doubles as the PDF file name and the share preview title.
export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const street = await streetsRepo.get(slug);
  return street ? { title: `${street.displayName} · CAMINA` } : {};
}

export default async function StreetDetailPage({ params }: Props) {
  const { city, slug } = await params;
  const street = await streetsRepo.get(slug);
  if (!street || street.city !== city) notFound();

  const to = await streetsRepo.now();
  const from = new Date(to.getTime() - 24 * 60 * 60_000);
  const [readings, history, metrics] = await Promise.all([
    streetsRepo.readings({ streetId: slug, from, to, bucketMinutes: 15 }),
    streetsRepo.readings({ streetId: slug, from: new Date(to.getTime() - HISTORY_WEEKS * WEEK_MS), to, bucketMinutes: 60 }),
    // v85 over the whole 24 h: a percentile is read from the summed speed
    // histograms, never averaged from the 15-min buckets' own v85.
    streetsRepo.latestMetrics({ city, metric: "counts", window: "24h", now: to }),
  ]);
  const v85 = metrics.find((m) => m.streetId === slug)?.v85Breakdown ?? {};
  const updated = dataUpdatedAt(readings, 15);

  return (
    <main className="mx-auto w-full max-w-[960px] px-4 py-8 sm:px-6 sm:py-10">
      <div className="flex items-center gap-3">
        <Link
          href={`/${city}?street=${encodeURIComponent(street.id)}` as never}
          className="inline-flex min-h-11 items-center text-sm print:hidden font-medium text-[var(--ink-1)] underline-offset-4 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--focus)]"
        >
          ← Map
        </Link>
        <span className="hidden text-xs font-semibold uppercase tracking-wide text-[var(--ink-2)] print:inline">CAMINA · Street report</span>
        {isMock && <MockBadge />}
        <ReportActions title={`${street.displayName} · CAMINA`} />
      </div>
      <h1 className="mt-4 text-[length:var(--t-xl)] font-bold leading-[34px] text-[var(--ink-1)]">
        {street.displayName}
      </h1>
      <p className="mt-2 text-sm text-[var(--ink-2)] sm:text-base">
        Last 24 hours · 15-min buckets · counts by road-user class
      </p>
      <p className="mt-1 text-sm text-[var(--ink-2)]">
        {updated ? <>Data updated <time dateTime={updated}>{formatDublinDateTime(updated)}</time></> : "No data yet"}
      </p>
      <p className="mt-3 hidden text-sm text-[var(--ink-1)] print:block">
        Road users counted by a CAMINA sensor on this street, in 15-minute windows. The sensor keeps counts only,
        never images. Values under 5 are hidden and left out of totals and averages. Times are Dublin time.
      </p>
      {isMock && <div className="mt-3"><MockNotice /></div>}

      <section className="mt-6">
        <StreetTimeSeries readings={readings} directions={streetDirections(street)} history={history} historyWeeks={HISTORY_WEEKS} v85={v85} />
      </section>
      <ReportSummary readings={readings} v85={v85} />
      <PrintFooter />
      <CreditFooter />
    </main>
  );
}

export const revalidate = 60;
