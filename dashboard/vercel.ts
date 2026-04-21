// Vercel project configuration (typed). Replaces vercel.json.
// Declares framework, headers, redirects, and scheduled cron jobs.
import { routes, type VercelConfig } from "@vercel/config/v1";

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
    routes.header("/(.*)", {
      "Strict-Transport-Security": "max-age=63072000; includeSubDomains; preload",
      "X-Content-Type-Options": "nosniff",
      "Referrer-Policy": "strict-origin-when-cross-origin",
      "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    }),
  ],
  redirects: [
    routes.redirect("/", "/dublin", { permanent: false }),
  ],
  crons: [
    { path: "/api/cron/refresh-aggregates", schedule: "*/5 * * * *" },
    { path: "/api/cron/detect-silent", schedule: "*/15 * * * *" },
    { path: "/api/cron/reconcile-daily", schedule: "0 1 * * *" },
  ],
};
