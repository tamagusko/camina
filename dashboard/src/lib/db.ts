import "server-only";
import { drizzle } from "drizzle-orm/postgres-js";
import postgres from "postgres";
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
  const client = postgres(url, { max: 5, prepare: false });
  _db = drizzle(client, { schema });
  return _db;
}
