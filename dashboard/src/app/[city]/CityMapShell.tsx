"use client";
import dynamic from "next/dynamic";
import { useMemo, useState } from "react";
import { StreetSidePanel } from "@/components/panels/StreetSidePanel";
import type { MetricValue, StreetSummary } from "@/lib/types";

// MapLibre touches `window` during init; load it browser-only to avoid any
// SSR/hydration interaction. This is the same pattern as antstackio/React-leaflet
// (page.tsx): `dynamic(() => import("..."), { ssr: false })`.
const StreetMap = dynamic(
  () => import("@/components/map/StreetMap").then((m) => m.StreetMap),
  {
    ssr: false,
    loading: () => (
      <div
        className="flex h-screen w-screen items-center justify-center bg-white text-body-gray"
        style={{ height: "100dvh", width: "100vw" }}
      >
        Loading map…
      </div>
    ),
  }
);

interface Props {
  city: string;
  streets: StreetSummary[];
  initialMetrics: MetricValue[];
}

export function CityMapShell({ city, streets, initialMetrics }: Props) {
  const [selected, setSelected] = useState<string | null>(null);
  // Freshest metrics, lifted from StreetMap so the side panel reflects the
  // latest auto-refreshed data instead of the server-rendered first paint.
  const [metrics, setMetrics] = useState<MetricValue[]>(initialMetrics);

  const streetById = useMemo(() => {
    const m = new Map<string, StreetSummary>();
    for (const s of streets) m.set(s.id, s);
    return m;
  }, [streets]);

  const selectedStreet = selected ? streetById.get(selected) ?? null : null;
  const selectedMetric = selected
    ? metrics.find((m) => m.streetId === selected) ?? null
    : null;

  return (
    <>
      <StreetMap
        city={city}
        streets={streets}
        initialMetrics={initialMetrics}
        onSelectStreet={setSelected}
        onMetricsChange={setMetrics}
      />
      <StreetSidePanel
        street={selectedStreet}
        metric={selectedMetric}
        onClose={() => setSelected(null)}
      />
    </>
  );
}
