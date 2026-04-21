import "server-only";
import { NextResponse } from "next/server";

// Rejects cron-route calls that don't come from Vercel Cron.
// Vercel signs cron requests via Authorization: Bearer <VERCEL_CRON_SECRET>.
export function verifyCron(request: Request): NextResponse | null {
  const secret = process.env.VERCEL_CRON_SECRET;
  if (!secret) return null; // Dev mode: skip check.
  const header = request.headers.get("authorization") ?? "";
  const matched = header.match(/^Bearer\s+(.+)$/i);
  if (matched?.[1] === secret) return null;
  return NextResponse.json({ error: "forbidden" }, { status: 403 });
}
