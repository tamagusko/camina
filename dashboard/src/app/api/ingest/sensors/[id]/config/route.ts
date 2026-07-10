import { NextResponse } from "next/server";
import { verifyIngestToken } from "@/lib/ingest-auth";
import { checkIngestRateLimit } from "@/lib/ingest-ratelimit";
import { readSensorConfig } from "@/lib/ingest-store";
import { isMock } from "@/lib/data-source";

interface Ctx {
  params: Promise<{ id: string }>;
}

const MOCK_CONFIG = {
  config_version: "mock-v1",
  publish_interval_minutes: 15,
  heartbeat_interval_minutes: 5,
  daily_publish_time_utc: "00:00",
  detection_zone: null,
  frame_skip: 5,
  min_track_hits: 3,
} as const;

export async function GET(request: Request, { params }: Ctx) {
  const { id } = await params;

  const limited = await checkIngestRateLimit(request, id);
  if (limited) return limited;

  const authError = await verifyIngestToken(request, id);
  if (authError) return authError;

  if (isMock) return NextResponse.json(MOCK_CONFIG);
  // Live mode: return the sensor's stored config (removes the 501 stub).
  const cfg = await readSensorConfig(id);
  if (!cfg) return NextResponse.json({ error: "unknown_sensor" }, { status: 404 });
  return NextResponse.json({ ...cfg.config, config_version: cfg.config_version });
}
