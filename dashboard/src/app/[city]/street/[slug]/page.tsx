import { notFound } from "next/navigation";
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

  const to = new Date();
  const from = new Date(to.getTime() - 24 * 60 * 60_000);
  const readings = await streetsRepo.readings({
    streetId: slug,
    from,
    to,
    bucketMinutes: 15,
  });

  return (
    <main className="mx-auto max-w-3xl px-6 py-10">
      <MockDataPill />
      <p className="text-caption uppercase tracking-wide text-muted-gray">Street</p>
      <h1 className="text-display mt-1">{street.displayName}</h1>
      <p className="text-body text-body-gray mt-2">
        Last 24 hours · 15-min buckets · counts by road-user class
      </p>

      <section className="mt-10">
        <StreetTimeSeries readings={readings} />
      </section>
    </main>
  );
}

export const revalidate = 60;
