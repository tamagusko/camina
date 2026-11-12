import { NextResponse } from "next/server";
import { heartbeatPayloadSchema } from "@/lib/schemas";
import { verifyIngestToken } from "@/lib/ingest-auth";
import { checkIngestRateLimit } from "@/lib/ingest-ratelimit";
import { checkTimestampSkew, persistHeartbeat, readSensorConfigVersion } from "@/lib/ingest-store";
import { isMock } from "@/lib/data-source";
import { MOCK_CONFIG } from "@/lib/mock-sensor-config";

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
  const parsed = heartbeatPayloadSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json({ error: "bad_payload", issues: parsed.error.issues }, { status: 400 });
  }
  if (parsed.data.sensor_id !== id) {
    return NextResponse.json({ error: "sensor_id_mismatch" }, { status: 400 });
  }
  const skew = checkTimestampSkew(parsed.data.ts);
  if (skew) return NextResponse.json({ error: skew.error }, { status: skew.status });

  if (isMock) {
    return NextResponse.json({ ok: true, latest_config_version: MOCK_CONFIG.config_version });
  }
  // Live mode: idempotent heartbeat upsert + latest-wins sensor pointer (H2).
  await persistHeartbeat(parsed.data, id);
  const latestConfigVersion = await readSensorConfigVersion(id);
  if (latestConfigVersion === null) {
    return NextResponse.json({ error: "unknown_sensor" }, { status: 404 });
  }
  return NextResponse.json({ ok: true, latest_config_version: latestConfigVersion });
}
