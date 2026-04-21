import { NextResponse } from "next/server";
import { verifyCron } from "@/lib/cron-auth";
import { isMock } from "@/lib/data-source";

export async function GET(request: Request) {
  const authError = verifyCron(request);
  if (authError) return authError;
  if (isMock) {
    return NextResponse.json({ ok: true, note: "mock mode — all sensors healthy" });
  }
  // Live mode: find sensors with last_heartbeat < NOW() - 15min and insert events.
  return NextResponse.json({ error: "live_mode_not_implemented" }, { status: 501 });
}
