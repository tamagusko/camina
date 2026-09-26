import { notFound } from "next/navigation";
import Link from "next/link";
import { MockDataPill } from "@/components/layout/MockDataPill";
import { StreetTimeSeries } from "@/components/charts/StreetTimeSeries";
import { streetsRepo } from "@/lib/repo";

interface Props {
  params: Promise<{ city: string; slug: string }>;
}

export default async function StreetDetailPage({ params }: Props) {
  const { city, slug } = await params;
  const street = await streetsRepo.get(slug);
  if (!street || street.city !== city) notFound();

  const to = await streetsRepo.now();
  const from = new Date(to.getTime() - 24 * 60 * 60_000);
  const readings = await streetsRepo.readings({
    streetId: slug,
    from,
    to,
    bucketMinutes: 15,
  });

  return (
    <main className="mx-auto w-full max-w-[960px] px-4 py-8 sm:px-6 sm:py-10">
      <MockDataPill placement="detail" />
      <Link
        href={`/${city}`}
        className="inline-flex min-h-11 items-center text-sm font-medium text-[var(--ink-1)] underline-offset-4 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--focus)]"
      >
        ← Map
      </Link>
      <h1 className="mt-4 text-[length:var(--t-xl)] font-bold leading-[34px] text-[var(--ink-1)]">
        {street.displayName}
      </h1>
      <p className="mt-2 text-sm text-[var(--ink-2)] sm:text-base">
        Last 24 hours · 15-min buckets · counts by road-user class
      </p>

      <section className="mt-6">
        <StreetTimeSeries readings={readings} />
      </section>
    </main>
  );
}

export const revalidate = 60;
