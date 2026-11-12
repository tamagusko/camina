import { NextResponse } from "next/server";
import { verifyCron } from "@/lib/cron-auth";
import { isMock } from "@/lib/data-source";
import { reconcileRecent } from "@/lib/reconcile-daily";

export async function GET(request: Request) {
  const authError = verifyCron(request);
  if (authError) return authError;
  if (isMock) {
    return NextResponse.json({ ok: true, note: "mock mode — reconciliation skipped" });
  }
  return NextResponse.json({ ok: true, ...(await reconcileRecent()) });
}
