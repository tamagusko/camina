import { notFound } from "next/navigation";
import { MockDataPill } from "@/components/layout/MockDataPill";
import { streetsRepo } from "@/lib/repo";
import { CITY_VIEWS } from "@/lib/geo";
import { CityMapShell } from "./CityMapShell";

interface Props {
  params: Promise<{ city: string }>;
}

export default async function CityPage({ params }: Props) {
  const { city } = await params;
  if (!(city in CITY_VIEWS)) notFound();

  const [streets, initialMetrics] = await Promise.all([
    streetsRepo.list(city),
    streetsRepo.latestMetrics({ city, metric: "counts", window: "1h" }),
  ]);

  return (
    <main
      className="relative h-screen w-screen"
      style={{ height: "100dvh", width: "100vw" }}
    >
      <MockDataPill />
      <CityMapShell city={city} streets={streets} initialMetrics={initialMetrics} />
    </main>
  );
}
