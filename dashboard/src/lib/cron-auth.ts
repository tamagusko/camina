import "server-only";
import { NextResponse } from "next/server";
import { isProduction } from "@/lib/env";
import { secureCompare } from "@/lib/secure-compare";

// Rejects cron-route calls that don't come from Vercel Cron.
// Vercel signs cron requests via Authorization: Bearer <VERCEL_CRON_SECRET>.
export function verifyCron(request: Request): NextResponse | null {
  const secret = process.env.VERCEL_CRON_SECRET;
  if (!secret) {
    // Fail closed in production: a missing secret must not open the routes.
    if (isProduction()) {
      return NextResponse.json({ error: "forbidden" }, { status: 403 });
    }
    return null; // Dev mode: skip check.
  }
  const header = request.headers.get("authorization") ?? "";
  const matched = header.match(/^Bearer\s+(.+)$/i);
  const token = matched?.[1];
  if (token && secureCompare(token, secret)) return null;
  return NextResponse.json({ error: "forbidden" }, { status: 403 });
}
