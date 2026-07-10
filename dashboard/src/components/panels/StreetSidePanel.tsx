"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { X } from "lucide-react";
import { cn } from "@/lib/cn";
import { formatDublinDateTime, formatDublinTime } from "@/lib/format-time";
import type { MetricValue, RoadUserClass, StreetAdminInfo, StreetSummary } from "@/lib/types";

interface Props {
  street: StreetSummary | null;
  metric: MetricValue | null;
  onClose: () => void;
}

const isDevAdmin =
  typeof process !== "undefined" &&
  process.env.NEXT_PUBLIC_CAMINA_DEV_ADMIN === "true";

function fmtNumber(n: number | null | undefined, opts?: Intl.NumberFormatOptions): string {
  if (n === null || n === undefined || !Number.isFinite(n)) return "—";
  return new Intl.NumberFormat("en-IE", opts).format(n);
}

function totalCount(m: MetricValue | null): number {
  if (!m) return 0;
  // Suppressed classes (null) contribute their k-floor-bounded minimum of 0 —
  // the published total is therefore a privacy-safe lower bound.
  return Object.values(m.classBreakdown).reduce<number>((a, b) => a + (b ?? 0), 0);
}

export function StreetSidePanel({ street, metric, onClose }: Props) {
  const [admin, setAdmin] = useState<StreetAdminInfo | null>(null);
  const [adminError, setAdminError] = useState<string | null>(null);

  useEffect(() => {
    if (!street || !isDevAdmin) {
      setAdmin(null);
      setAdminError(null);
      return;
    }
    let cancelled = false;
    setAdminError(null);
    fetch(`/api/admin/streets/${street.id}/info`, { cache: "no-store" })
      .then(async (r) => {
        if (!r.ok) throw new Error(`${r.status}`);
        return (await r.json()) as StreetAdminInfo;
      })
      .then((data) => !cancelled && setAdmin(data))
      .catch((err) => !cancelled && setAdminError(err.message ?? "error"));
    return () => {
      cancelled = true;
    };
  }, [street]);

  if (!street) return null;

  const total = totalCount(metric);
  // null = suppressed (had 1..4, shown as "<5"); 0 = genuinely no traffic
  // (hidden). Sort suppressed rows just below the smallest published count.
  const perClass = metric
    ? (Object.entries(metric.classBreakdown) as [RoadUserClass, number | null][])
        .filter(([, n]) => n === null || n > 0)
        .sort((a, b) => (b[1] ?? 0) - (a[1] ?? 0))
    : [];

  return (
    <div
      className={cn(
        "pointer-events-auto fixed z-30 bg-white shadow-medium overflow-y-auto",
        "md:right-0 md:top-0 md:h-full md:w-[400px] md:rounded-none",
        "inset-x-0 bottom-0 rounded-t-feature max-h-[75dvh] md:inset-auto md:max-h-none"
      )}
      role="dialog"
      aria-label={street.displayName}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-4 p-6">
        <div>
          <p className="text-micro uppercase tracking-wide text-muted-gray">Street</p>
          <h2 className="text-sub leading-tight text-black">{street.displayName}</h2>
        </div>
        <button
          onClick={onClose}
          aria-label="Close"
          className="inline-flex h-10 w-10 items-center justify-center rounded-pill hover:bg-hover-light"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      {/* Silent-sensor notice — a stale sensor must not read as a quiet street. */}
      {metric?.stale && (
        <div className="mx-6 mb-3 rounded-card border border-chip-gray bg-chip-gray px-4 py-3">
          <p className="text-micro uppercase tracking-wide text-body-gray">Sensor status</p>
          <p className="mt-1 text-caption text-black">
            No recent data
            {metric.lastSeen ? ` · last seen ${formatDublinTime(metric.lastSeen)}` : ""}
          </p>
        </div>
      )}

      {/* Headline stats */}
      <div className="grid grid-cols-2 gap-3 px-6 pb-4">
        <div className="rounded-card bg-chip-gray p-4">
          <p className="text-micro uppercase tracking-wide text-body-gray">Total count</p>
          <p className="mt-1 text-card tabular-nums leading-none">{fmtNumber(total)}</p>
        </div>
        <div className="rounded-card bg-chip-gray p-4">
          <p className="text-micro uppercase tracking-wide text-body-gray">Avg speed</p>
          <p className="mt-1 text-card tabular-nums leading-none">
            {metric?.avgSpeedKmh !== null && metric?.avgSpeedKmh !== undefined
              ? `${fmtNumber(metric.avgSpeedKmh, { maximumFractionDigits: 1 })} km/h`
              : "—"}
          </p>
        </div>
      </div>

      {/* Per-class breakdown */}
      <div className="px-6 pb-4">
        <p className="text-micro uppercase tracking-wide text-body-gray mb-2">By class</p>
        {perClass.length === 0 ? (
          <p className="text-caption text-muted-gray">No data in the selected window.</p>
        ) : (
          <dl className="divide-y divide-chip-gray">
            <div className="grid grid-cols-3 py-2 text-micro uppercase tracking-wide text-muted-gray">
              <span>Class</span>
              <span className="text-right">Count</span>
              <span className="text-right">Speed (km/h)</span>
            </div>
            {perClass.map(([cls, n]) => {
              const speed = metric?.speedBreakdown[cls];
              return (
                <div key={cls} className="grid grid-cols-3 py-2 text-caption">
                  <dt className="capitalize text-black">{cls.replace("_", " ")}</dt>
                  <dd className="text-right tabular-nums font-medium">
                    {n === null ? (
                      <span className="text-muted-gray" title="Suppressed below the k-anonymity floor (fewer than 5)">
                        &lt;5
                      </span>
                    ) : (
                      fmtNumber(n)
                    )}
                  </dd>
                  <dd className="text-right tabular-nums text-body-gray">
                    {speed !== null && speed !== undefined
                      ? fmtNumber(speed, { maximumFractionDigits: 1 })
                      : "—"}
                  </dd>
                </div>
              );
            })}
          </dl>
        )}
      </div>

      {/* Admin (dev) section */}
      {isDevAdmin && (
        <AdminSection info={admin} error={adminError} />
      )}

      <div className="border-t border-chip-gray px-6 py-4">
        <Link
          href={`/${street.city}/street/${street.id}` as never}
          className="btn-primary w-full"
        >
          Open detailed view
        </Link>
      </div>
    </div>
  );
}

function AdminSection({
  info,
  error,
}: {
  info: StreetAdminInfo | null;
  error: string | null;
}) {
  return (
    <div className="border-t border-chip-gray bg-black text-white px-6 py-5">
      <p className="text-micro uppercase tracking-wide text-muted-gray">
        Admin · Sensors on this street
      </p>
      {error && (
        <p className="mt-2 text-caption text-muted-gray">
          Unable to load admin info ({error}).
        </p>
      )}
      {!error && !info && (
        <p className="mt-2 text-caption text-muted-gray">Loading…</p>
      )}
      {info && info.sensors.length === 0 && (
        <p className="mt-2 text-caption text-muted-gray">
          No sensors mapped to this street yet.
        </p>
      )}
      {info?.sensors.map((s) => (
        <div key={s.id} className="mt-3 rounded-card bg-white/5 p-3 text-caption">
          <div className="flex items-center justify-between">
            <span className="font-mono text-white">{s.id}</span>
            <span
              className={cn(
                "rounded-pill px-2 py-0.5 text-micro",
                s.active ? "bg-white text-black" : "bg-muted-gray text-black"
              )}
            >
              {s.active ? "active" : "inactive"}
            </span>
          </div>
          <dl className="mt-2 grid grid-cols-2 gap-y-1 text-muted-gray">
            <dt>Display name</dt>
            <dd className="text-white text-right truncate">{s.displayName}</dd>
            <dt>Installed</dt>
            <dd className="text-white text-right">{s.installDate}</dd>
            <dt>GPS</dt>
            <dd className="text-white text-right tabular-nums">
              {s.latitude.toFixed(4)}, {s.longitude.toFixed(4)}
            </dd>
            <dt>Firmware</dt>
            <dd className="text-white text-right font-mono">{s.fwVersion}</dd>
            <dt>Config</dt>
            <dd className="text-white text-right font-mono">{s.configVersion}</dd>
            <dt>Last heartbeat</dt>
            <dd className="text-white text-right tabular-nums">
              {s.lastHeartbeat ? formatDublinDateTime(s.lastHeartbeat) : "—"}
            </dd>
          </dl>
        </div>
      ))}
    </div>
  );
}
