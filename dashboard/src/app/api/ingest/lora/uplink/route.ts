import "server-only";
import { NextResponse } from "next/server";
import { z } from "zod";
import { waitUntil } from "@vercel/functions";
import { isProduction } from "@/lib/env";
import { isMock } from "@/lib/data-source";
import { secureCompare } from "@/lib/secure-compare";
import { decodeLoraPayload, LoraDecodeError } from "@/lib/lora-codec";
import type { CountsPayload } from "@/lib/schemas";
import { persistCounts, refreshBoundedAggregatesSafe } from "@/lib/ingest-store";

// TTN (The Things Network) LoRaWAN uplink webhook.
//
// TTN delivers each decoded uplink as a POST here. Authenticity is proven by a
// shared secret sent in a custom header (TTN webhooks support additional
// headers): `X-Camina-Webhook-Key` must match `TTN_WEBHOOK_KEY`. We follow the
// same fail-closed idiom as cron-auth.ts — a missing secret rejects in
// production and only skips the check in dev.
//
// The binary frame (see @/lib/lora-codec + docs/lora.md) carries the same
// nine-class window as the HTTPS counts path, so a live uplink persists through
// the identical idempotent upsert (`persistCounts`); duplicate TTN uplinks are
// naturally deduped by the composite primary key.

const WEBHOOK_HEADER = "x-camina-webhook-key";
const WINDOW_SECONDS = 900; // LoRa windows are fixed 15 min; window_end derived.

// Minimal TTN uplink envelope — only the fields we consume are validated.
const ttnUplinkSchema = z.object({
  end_device_ids: z.object({ device_id: z.string() }),
  uplink_message: z.object({ frm_payload: z.string() }),
  received_at: z.string().optional(),
});

/**
 * Verify the TTN shared-secret header (timing-safe). Returns a rejection
 * response, or null when the request is authentic / dev-skipped.
 */
export function verifyWebhookKey(request: Request): NextResponse | null {
  const secret = process.env.TTN_WEBHOOK_KEY;
  if (!secret) {
    // Fail closed in production; only skip the check in dev when unset.
    if (isProduction()) {
      return NextResponse.json({ error: "forbidden" }, { status: 403 });
    }
    return null;
  }
  const presented = request.headers.get(WEBHOOK_HEADER) ?? "";
  if (presented && secureCompare(presented, secret)) return null;
  return NextResponse.json({ error: "forbidden" }, { status: 403 });
}

/**
 * Thin adapter: shape the decoded LoRa window into the CountsPayload the shared
 * persistence path expects, then upsert. Kept in the route so ingest-store.ts
 * stays untouched. LoRa frames carry no speeds, so `avg_speed_kmh` is empty.
 */
async function persistLoraWindow(
  sensorId: string,
  windowStartIso: string,
  counts: Record<string, number>,
  producedAtIso: string
): Promise<void> {
  const windowEndIso = new Date(
    Date.parse(windowStartIso) + WINDOW_SECONDS * 1000
  ).toISOString();
  // Persist only non-zero classes, matching the HTTPS/fixture convention that a
  // reading row exists only for a class that was actually observed.
  const nonZero = Object.fromEntries(
    Object.entries(counts).filter(([, v]) => v > 0)
  );
  const payload: CountsPayload = {
    schema_version: "lora-2",
    sensor_id: sensorId,
    window_start: windowStartIso,
    window_end: windowEndIso,
    partial: false,
    counts: nonZero,
    avg_speed_kmh: {},
    config_version: "lora",
    fw_version: "lora",
    produced_at: producedAtIso,
  };
  await persistCounts(payload, sensorId);
}

export async function POST(request: Request) {
  const authError = verifyWebhookKey(request);
  if (authError) return authError;

  const body = await request.json().catch(() => null);
  const parsed = ttnUplinkSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json(
      { error: "bad_uplink", issues: parsed.error.issues },
      { status: 400 }
    );
  }

  let decoded: ReturnType<typeof decodeLoraPayload>;
  try {
    decoded = decodeLoraPayload(parsed.data.uplink_message.frm_payload);
  } catch (err) {
    if (err instanceof LoraDecodeError) {
      return NextResponse.json(
        { error: "bad_payload", detail: err.message },
        { status: 400 }
      );
    }
    throw err;
  }

  // Camera id encoded in the frame is the authoritative sensor id (same "D01"
  // form the HTTPS routes key on). The TTN device_id is informational.
  const sensorId = decoded.cameraId;
  const producedAt = parsed.data.received_at ?? new Date().toISOString();

  if (isMock) {
    // Mock mode: validate + acknowledge, never persist (fixtures are truth).
    return NextResponse.json(
      { ok: true, source: "lora", mode: "mock", sensor_id: sensorId },
      { status: 202 }
    );
  }

  // Live mode: idempotent upsert through the shared counts persistence path.
  await persistLoraWindow(
    sensorId,
    decoded.windowStart,
    decoded.counts,
    producedAt
  );
  waitUntil(refreshBoundedAggregatesSafe());
  return NextResponse.json(
    { ok: true, source: "lora", sensor_id: sensorId },
    { status: 202 }
  );
}
