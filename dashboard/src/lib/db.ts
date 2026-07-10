import "server-only";
import { attachDatabasePool } from "@vercel/functions";
import { drizzle } from "drizzle-orm/postgres-js";
import postgres from "postgres";
import { isProduction } from "@/lib/env";
import * as schema from "../../drizzle/schema";

// Lazy singleton — the client is only constructed when the live data source
// is selected. Keeps mock-mode deploys free of DB dependencies.

let _db: ReturnType<typeof drizzle> | null = null;

export function db() {
  if (_db) return _db;
  const url = process.env.DATABASE_URL;
  if (!url) {
    throw new Error(
      "DATABASE_URL missing. Set CAMINA_DATA_SOURCE=mock for dev, or configure Postgres."
    );
  }
  // Neon serves pooled connections on a distinct `-pooler` host. Fluid Compute
  // spins up many short-lived function instances; hitting the direct endpoint
  // exhausts Postgres connection slots. Fail closed in production (H13).
  if (isProduction() && !url.includes("-pooler")) {
    throw new Error(
      "DATABASE_URL must point at the Neon pooled endpoint (host contains '-pooler') in production."
    );
  }
  // max:2 — Fluid Compute reuses instances but scales horizontally; a small
  // per-instance pool multiplied across instances still respects Neon limits.
  const client = postgres(url, { max: 2, prepare: false });
  // Drain in-flight queries when Vercel suspends the instance (M2 mandate).
  attachDatabasePool(client);
  _db = drizzle(client, { schema });
  return _db;
}
