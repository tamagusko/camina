import { NextResponse } from "next/server";
import { verifyCron } from "@/lib/cron-auth";
import { isMock } from "@/lib/data-source";

export async function GET(request: Request) {
  const authError = verifyCron(request);
  if (authError) return authError;
  if (isMock) {
    return NextResponse.json({ ok: true, note: "mock mode — reconciliation skipped" });
  }
  // Live mode: compare sum(sensor_readings) vs sensor_daily_totals for yesterday
  // and flag mismatches per docs/RECONCILIATION.md.
  return NextResponse.json({ error: "live_mode_not_implemented" }, { status: 501 });
}
