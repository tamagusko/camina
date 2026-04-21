import "server-only";
import { NextResponse } from "next/server";

// Minimal per-device Bearer-token check for ingest routes.
// Live mode will lookup sensors.api_token_hash via Drizzle and bcrypt-compare;
// for now, dev allows a shared DEV token so the Python sensor daemon can be
// pointed at the dashboard without wiring a DB.

const DEV_TOKEN = process.env.CAMINA_DEV_INGEST_TOKEN;

export function verifyIngestToken(
  request: Request,
  sensorId: string
): NextResponse | null {
  const header = request.headers.get("authorization") ?? "";
  const matched = header.match(/^Bearer\s+(.+)$/i);
  const token = matched?.[1];

  if (!token) {
    return NextResponse.json({ error: "missing_token" }, { status: 401 });
  }
  if (DEV_TOKEN && token === DEV_TOKEN) return null;

  // Live mode hook goes here.
  return NextResponse.json(
    { error: "invalid_token", sensor_id: sensorId },
    { status: 401 }
  );
}
