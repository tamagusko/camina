import "server-only";
import type { StreetsRepo } from "./types";

// Live Postgres-backed repository. Stub for now — implementation lands when
// the Neon database is connected (see plan/02-dashboard-vercel.md §8).

export const liveStreetsRepo: StreetsRepo = {
  async list() {
    throw new Error("Live streets repo not implemented. Set CAMINA_DATA_SOURCE=mock.");
  },
  async get() {
    throw new Error("Live streets repo not implemented. Set CAMINA_DATA_SOURCE=mock.");
  },
  async readings() {
    throw new Error("Live streets repo not implemented. Set CAMINA_DATA_SOURCE=mock.");
  },
  async latestMetrics() {
    throw new Error("Live streets repo not implemented. Set CAMINA_DATA_SOURCE=mock.");
  },
  async adminInfo() {
    throw new Error("Live streets repo not implemented. Set CAMINA_DATA_SOURCE=mock.");
  },
};
