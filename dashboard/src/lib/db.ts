import "server-only";
import { drizzle } from "drizzle-orm/postgres-js";
import postgres from "postgres";
import * as schema from "../../drizzle/schema";

// Lazy singleton — the client is only constructed when the live data source
// is selected. Keeps mock-mode deploys free of DB dependencies.

let _db: ReturnType<typeof drizzle> | null = null;

/**
 * Neon serves pooled connections on a host whose first label ends in
 * `-pooler` (ep-name-123-pooler.region.aws.neon.tech). Fluid Compute spins up
 * many short-lived instances, and the direct endpoint runs out of Postgres
 * connection slots, so a deployed Vercel function (production or preview)
 * fails closed on any other host (H13). Off Vercel (local `next start`,
 * `vercel dev`, tests) any URL is allowed. Returns the error, or null.
 */
export function pooledUrlError(url: string, vercelEnv: string | undefined): string | null {
  if (vercelEnv !== "production" && vercelEnv !== "preview") return null;
  let host: string;
  try {
    host = new URL(url).hostname;
  } catch {
    host = "";
  }
  return host.split(".")[0]?.endsWith("-pooler")
    ? null
    : "DATABASE_URL must point at the Neon pooled endpoint (hostname ending '-pooler') on Vercel.";
}

export function db() {
  if (_db) return _db;
  const url = process.env.DATABASE_URL;
  if (!url) {
    throw new Error(
      "DATABASE_URL missing. Set CAMINA_DATA_SOURCE=mock for dev, or configure Postgres."
    );
  }
  const poolerError = pooledUrlError(url, process.env.VERCEL_ENV);
  if (poolerError) throw new Error(poolerError);
  // max:2 — Fluid Compute reuses instances but scales horizontally; a small
  // per-instance pool multiplied across instances still respects Neon limits.
  // Postgres.js manages its own pool. Vercel's attachDatabasePool only accepts
  // event-emitting pools (pg/mysql), not a Postgres.js client.
  const client = postgres(url, { max: 2, prepare: false, idle_timeout: 20 });
  _db = drizzle(client, { schema });
  return _db;
}
