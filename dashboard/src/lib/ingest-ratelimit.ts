import "server-only";
import { NextResponse } from "next/server";
import { Ratelimit } from "@upstash/ratelimit";
import { Redis } from "@upstash/redis";

// Ingest rate limiting (M17). Gated on Upstash env presence: with no
// UPSTASH_REDIS_REST_URL/TOKEN configured (Hobby/dev), the limiter is skipped.
// A sensor legitimately posts ~1 req/15 min plus buffered replays, so the
// window is generous: 60 requests/hour per (sensor-id + client IP).

let _limiter: Ratelimit | null | undefined;

function limiter(): Ratelimit | null {
  if (_limiter !== undefined) return _limiter;
  const url = process.env.UPSTASH_REDIS_REST_URL;
  const token = process.env.UPSTASH_REDIS_REST_TOKEN;
  if (!url || !token) {
    _limiter = null;
    return null;
  }
  _limiter = new Ratelimit({
    redis: new Redis({ url, token }),
    limiter: Ratelimit.slidingWindow(60, "1 h"),
    prefix: "camina:ingest",
    analytics: false,
  });
  return _limiter;
}

function clientIp(request: Request): string {
  const xff = request.headers.get("x-forwarded-for");
  if (xff) {
    const first = xff.split(",")[0];
    if (first) return first.trim();
  }
  return request.headers.get("x-real-ip") ?? "unknown";
}

export async function checkIngestRateLimit(
  request: Request,
  sensorId: string
): Promise<NextResponse | null> {
  const rl = limiter();
  if (!rl) return null; // No Upstash configured: skip.
  const key = `${sensorId}:${clientIp(request)}`;
  const { success, limit, remaining, reset } = await rl.limit(key);
  if (success) return null;
  const retryAfter = Math.max(0, Math.ceil((reset - Date.now()) / 1000));
  return NextResponse.json(
    { error: "rate_limited" },
    {
      status: 429,
      headers: {
        "Retry-After": String(retryAfter),
        "X-RateLimit-Limit": String(limit),
        "X-RateLimit-Remaining": String(remaining),
      },
    }
  );
}
