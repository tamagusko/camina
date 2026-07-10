import { NextResponse } from "next/server";
import { verifyCron } from "@/lib/cron-auth";
import { isMock } from "@/lib/data-source";
import { runRetention } from "./retention-core";

// Daily retention job (audit C1). Scheduled at 03:00 UTC via vercel.ts — a
// daily cadence that the Vercel Hobby plan honours. Rolls raw sensor_readings
// older than 90 days into the durable street_hourly / street_daily aggregates,
// then deletes them, in bounded advisory-lock-guarded batches.
export async function GET(request: Request): Promise<NextResponse> {
  const authError = verifyCron(request);
  if (authError) return authError;

  if (isMock) {
    return NextResponse.json({ ok: true, note: "mock mode — retention skipped" });
  }

  const result = await runRetention();
  // Log rows rolled/deleted (structured, one line — captured by Vercel logs).
  console.info(
    `[cron/retention] batches=${result.batches} rowsDeleted=${result.rowsDeleted} ` +
      `hourlyUpserts=${result.hourlyUpserts} dailyUpserts=${result.dailyUpserts} ` +
      `skippedLocked=${result.skippedLocked}`
  );
  return NextResponse.json({ ok: true, ...result });
}
