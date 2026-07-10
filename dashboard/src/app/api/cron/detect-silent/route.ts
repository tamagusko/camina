import { NextResponse } from "next/server";
import { isNull, lt, or } from "drizzle-orm";
import { verifyCron } from "@/lib/cron-auth";
import { isMock } from "@/lib/data-source";
import { db } from "@/lib/db";
import { sensors } from "../../../../../drizzle/schema";

// A sensor is silent after 3 missed heartbeats (600 s interval → 30 min).
// Matches the repo layer's STALE_AFTER_MS so ops and public UI agree.
const SILENT_AFTER_MS = 30 * 60 * 1000;

export async function GET(request: Request) {
  const authError = verifyCron(request);
  if (authError) return authError;
  if (isMock) {
    return NextResponse.json({ ok: true, note: "mock mode — all sensors healthy" });
  }
  const cutoff = new Date(Date.now() - SILENT_AFTER_MS);
  const silent = await db()
    .select({ id: sensors.id, lastHeartbeat: sensors.lastHeartbeat })
    .from(sensors)
    .where(or(isNull(sensors.lastHeartbeat), lt(sensors.lastHeartbeat, cutoff)));
  if (silent.length > 0) {
    console.warn(
      `[detect-silent] ${silent.length} sensor(s) silent > 30 min:`,
      silent.map((s) => s.id).join(", ")
    );
  }
  return NextResponse.json({
    ok: true,
    silentCount: silent.length,
    silent: silent.map((s) => ({
      id: s.id,
      lastHeartbeat: s.lastHeartbeat?.toISOString() ?? null,
    })),
  });
}
