import { NextResponse } from "next/server";
import { waitUntil } from "@vercel/functions";
import { countsPayloadSchema } from "@/lib/schemas";
import { verifyIngestToken } from "@/lib/ingest-auth";
import { checkIngestRateLimit } from "@/lib/ingest-ratelimit";
import {
  checkTimestampSkew,
  persistCounts,
  refreshBoundedAggregatesSafe,
} from "@/lib/ingest-store";
import { isMock } from "@/lib/data-source";

interface Ctx {
  params: Promise<{ id: string }>;
}

export async function POST(request: Request, { params }: Ctx) {
  const { id } = await params;

  const limited = await checkIngestRateLimit(request, id);
  if (limited) return limited;

  const authError = await verifyIngestToken(request, id);
  if (authError) return authError;

  const body = await request.json().catch(() => null);
  const parsed = countsPayloadSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json({ error: "bad_payload", issues: parsed.error.issues }, { status: 400 });
  }
  if (parsed.data.sensor_id !== id) {
    return NextResponse.json({ error: "sensor_id_mismatch" }, { status: 400 });
  }
  // Server-side skew policy (tighter than zod): 60 s future, 7 day past (H5).
  const skew = checkTimestampSkew(parsed.data.window_end);
  if (skew) return NextResponse.json({ error: skew.error }, { status: skew.status });

  if (isMock) {
    // In mock mode we accept but don't persist — fixtures are the source of truth.
    return NextResponse.json({ ok: true, latest_config_version: parsed.data.config_version });
  }
  // Live mode: idempotent fan-out upsert into sensor_readings (H2).
  await persistCounts(parsed.data, id);
  // Piggyback the bounded-MV refresh (H14): rate-gated + advisory-locked, run
  // as background work so it never blocks or fails the ingest response.
  waitUntil(refreshBoundedAggregatesSafe());
  return NextResponse.json({ ok: true, latest_config_version: parsed.data.config_version });
}
