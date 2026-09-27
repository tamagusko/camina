import "server-only";
import { NextResponse } from "next/server";
import { isProduction } from "@/lib/env";
import { secureCompare } from "@/lib/secure-compare";

// Rejects cron-route calls that carry no configured cron secret.
// Vercel Cron sends Authorization: Bearer <CRON_SECRET> (it reads only that
// env var name); the GitHub Actions cron sends Bearer <VERCEL_CRON_SECRET>.
export function verifyCron(request: Request): NextResponse | null {
  const secrets = [process.env.CRON_SECRET, process.env.VERCEL_CRON_SECRET].filter(
    (secret): secret is string => Boolean(secret)
  );
  if (secrets.length === 0) {
    // Fail closed in production: a missing secret must not open the routes.
    if (isProduction()) {
      return NextResponse.json({ error: "forbidden" }, { status: 403 });
    }
    return null; // Dev mode: skip check.
  }
  const header = request.headers.get("authorization") ?? "";
  const matched = header.match(/^Bearer\s+(.+)$/i);
  const token = matched?.[1];
  if (token && secrets.some((secret) => secureCompare(token, secret))) return null;
  return NextResponse.json({ error: "forbidden" }, { status: 403 });
}
