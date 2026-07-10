import { NextResponse } from "next/server";
import { verifyCron } from "@/lib/cron-auth";
import { isMock } from "@/lib/data-source";
import { refreshBoundedAggregates } from "@/lib/ingest-store";

// Sub-daily MV refresh fallback (H14). Vercel Hobby cron is daily-only, so this
// route is driven by the external GitHub Actions cron (.github/workflows/cron.yml,
// every ~15 min) rather than by vercel.ts. The primary refresh path is the
// ingest piggyback; this fills quiet periods. minIntervalMs=0 → always refresh
// when the cron fires (still advisory-lock guarded against overlap).
export async function GET(request: Request): Promise<NextResponse> {
  const authError = verifyCron(request);
  if (authError) return authError;
  if (isMock) {
    return NextResponse.json({ ok: true, note: "mock mode — no aggregates to refresh" });
  }
  const outcome = await refreshBoundedAggregates(undefined, { minIntervalMs: 0 });
  return NextResponse.json({ ok: true, outcome });
}
