"use client";
import dynamic from "next/dynamic";
import { useEffect, useMemo, useRef, useState } from "react";
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
        className="flex h-screen w-screen items-center justify-center bg-bg text-ink-2"
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
  mock: boolean;
}

export function CityMapShell({ city, streets, initialMetrics, mock }: Props) {
  const [selected, setSelected] = useState<string | null>(null);
  const triggerRef = useRef<HTMLElement | null>(null);
  const [panelMetric, setPanelMetric] = useState<MetricValue | null>(null);

  const streetById = useMemo(() => {
    const m = new Map<string, StreetSummary>();
    for (const s of streets) m.set(s.id, s);
    return m;
  }, [streets]);

  const selectedStreet = selected ? streetById.get(selected) ?? null : null;
  useEffect(() => {
    if (!selected) return;
    const url = `/api/metrics?city=${encodeURIComponent(city)}&metric=counts&window=now`;
    let cancelled = false;
    fetch(url, { cache: "no-store" }).then((response) => response.ok ? response.json() as Promise<MetricValue[]> : []).then((rows) => {
      if (!cancelled) setPanelMetric(rows.find((row) => row.streetId === selected) ?? null);
    }).catch(() => {});
    return () => { cancelled = true; };
  }, [city, selected]);
  function selectStreet(id: string) {
    triggerRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    setPanelMetric(initialMetrics.find((row) => row.streetId === id) ?? null);
    setSelected(id);
  }
  function closeStreet() {
    setSelected(null);
    requestAnimationFrame(() => {
      const trigger = triggerRef.current?.isConnected ? triggerRef.current : [...document.querySelectorAll<HTMLElement>('button[aria-controls="streets-list"]')].find((button) => button.offsetParent !== null);
      trigger?.focus();
    });
  }

  return (
    <>
      <StreetMap
        city={city}
        streets={streets}
        initialMetrics={initialMetrics}
        mock={mock}
        selectedId={selected}
        onSelectStreet={selectStreet}
      />
      <StreetSidePanel
        // Remount per street: the panel's admin state then starts empty for
        // each selection, instead of being reset inside an effect.
        key={selectedStreet?.id ?? "none"}
        street={selectedStreet}
        metric={panelMetric}
        onClose={closeStreet}
      />
    </>
  );
}
