import "server-only";
import { isProduction } from "@/lib/env";

// Selects the data source at server-start time.
// Honoured by every API route and server-component data-access function.

export type DataSource = "mock" | "live";

const env = process.env.CAMINA_DATA_SOURCE?.toLowerCase();

function resolveDataSource(): DataSource {
  if (env === "live") return "live";
  if (env === "mock") return "mock";
  // Fail closed: production must opt in explicitly. An unset or invalid
  // value silently serving mock data would mask a dead deployment.
  // Skipped during `next build` (which always sets NODE_ENV=production):
  // local/CI builds must not require deploy env vars. A misconfigured
  // production deploy still fails closed at the first runtime request.
  if (isProduction() && process.env.NEXT_PHASE !== "phase-production-build") {
    throw new Error(
      `CAMINA_DATA_SOURCE must be "live" or "mock" in production, got ${
        env === undefined ? "unset" : `"${env}"`
      }. Set it in the Vercel project environment.`
    );
  }
  return "mock"; // Dev/test default.
}

export const dataSource: DataSource = resolveDataSource();

export const isMock = dataSource === "mock";
export const isLive = dataSource === "live";

export const mockCity = process.env.CAMINA_MOCK_CITY ?? "dublin";
