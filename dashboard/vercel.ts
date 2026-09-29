// Vercel project configuration (typed). Replaces vercel.json.
// Declares framework, headers, redirects, and scheduled cron jobs.
import { routes, type Redirect, type VercelConfig } from "@vercel/config/v1";

// Observe violations on a preview deploy before enforcing this policy.
const cspReportOnly = [
  "default-src 'self'",
  "base-uri 'self'",
  "object-src 'none'",
  "frame-ancestors 'none'",
  "form-action 'self' https://accounts.google.com",
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline'",
  "font-src 'self' data:",
  "img-src 'self' data: blob: https://tiles.openfreemap.org https://*.googleusercontent.com",
  "connect-src 'self' https://tiles.openfreemap.org https://accounts.google.com",
  "worker-src 'self' blob:",
  "child-src 'self' blob:",
].join("; ");

export const config: VercelConfig = {
  framework: "nextjs",
  buildCommand: "pnpm build",
  headers: [
    routes.cacheControl("/basemap/(.*)", {
      public: true,
      maxAge: "1 week",
      immutable: true,
    }),
    // Security headers applied to all pages.
    routes.header("/(.*)", [
      { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains; preload" },
      { key: "X-Content-Type-Options", value: "nosniff" },
      { key: "X-Frame-Options", value: "DENY" },
      { key: "Content-Security-Policy-Report-Only", value: cspReportOnly },
      { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
      { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
    ]),
  ],
  redirects: [
    { source: "/", destination: "/dublin", permanent: false } satisfies Redirect,
  ],
  // Vercel Hobby honours DAILY cron granularity only (H14). Sub-daily jobs
  // (refresh-aggregates, detect-silent) are driven externally by GitHub Actions
  // (.github/workflows/cron.yml); MV refresh is also piggybacked on ingest.
  crons: [
    { path: "/api/cron/retention", schedule: "0 3 * * *" },
    { path: "/api/cron/reconcile-daily", schedule: "0 1 * * *" },
  ],
};
