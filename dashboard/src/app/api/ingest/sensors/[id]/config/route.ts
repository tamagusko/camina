import { NextResponse } from "next/server";
import { verifyIngestToken } from "@/lib/ingest-auth";
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
  const authError = verifyIngestToken(request, id);
  if (authError) return authError;

  if (isMock) return NextResponse.json(MOCK_CONFIG);
  return NextResponse.json({ error: "live_mode_not_implemented" }, { status: 501 });
}
