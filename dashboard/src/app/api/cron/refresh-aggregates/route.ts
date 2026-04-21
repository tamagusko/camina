import { NextResponse } from "next/server";
import { verifyCron } from "@/lib/cron-auth";
import { isMock } from "@/lib/data-source";

export async function GET(request: Request) {
  const authError = verifyCron(request);
  if (authError) return authError;
  if (isMock) {
    return NextResponse.json({ ok: true, note: "mock mode — no aggregates to refresh" });
  }
  // Live mode: REFRESH MATERIALIZED VIEW CONCURRENTLY street_readings_15m, then hourly.
  return NextResponse.json({ error: "live_mode_not_implemented" }, { status: 501 });
}
