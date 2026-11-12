import { NextResponse } from "next/server";
import { isNull, lt, or } from "drizzle-orm";
import { verifyCron } from "@/lib/cron-auth";
import { isMock } from "@/lib/data-source";
import { db } from "@/lib/db";
import { heartbeatMinutes, silentAfterMs } from "@/lib/heartbeat";
import { sensors } from "../../../../../drizzle/schema";

// A sensor is silent after 3 missed heartbeats; the interval is the one
// deployment setting CAMINA_HEARTBEAT_MINUTES (src/lib/heartbeat.ts).

export async function GET(request: Request) {
  const authError = verifyCron(request);
  if (authError) return authError;
  if (isMock) {
    return NextResponse.json({ ok: true, note: "mock mode — all sensors healthy" });
  }
  const minutes = heartbeatMinutes();
  const cutoff = new Date(Date.now() - silentAfterMs(minutes));
  const silent = await db()
    .select({ id: sensors.id, lastHeartbeat: sensors.lastHeartbeat })
    .from(sensors)
    .where(or(isNull(sensors.lastHeartbeat), lt(sensors.lastHeartbeat, cutoff)));
  if (silent.length > 0) {
    console.warn(
      `[detect-silent] ${silent.length} sensor(s) silent > ${3 * minutes} min:`,
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
