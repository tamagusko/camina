import { beforeEach, describe, expect, it, vi } from "vitest";

const { readSensorConfigVersion } = vi.hoisted(() => ({
  readSensorConfigVersion: vi.fn(),
}));

vi.mock("@/lib/data-source", () => ({ isMock: false }));
vi.mock("@/lib/ingest-auth", () => ({ verifyIngestToken: vi.fn().mockResolvedValue(null) }));
vi.mock("@/lib/ingest-ratelimit", () => ({ checkIngestRateLimit: vi.fn().mockResolvedValue(null) }));
vi.mock("@vercel/functions", () => ({ waitUntil: vi.fn() }));
vi.mock("@/lib/ingest-store", () => ({
  checkTimestampSkew: vi.fn().mockReturnValue(null),
  persistCounts: vi.fn().mockResolvedValue(undefined),
  persistHeartbeat: vi.fn().mockResolvedValue(undefined),
  persistDaily: vi.fn().mockResolvedValue(undefined),
  refreshBoundedAggregatesSafe: vi.fn().mockResolvedValue(undefined),
  readSensorConfigVersion,
}));

const ctx = { params: Promise.resolve({ id: "D01" }) };
const now = Date.now();
const payloads = {
  counts: {
    schema_version: "1.0",
    sensor_id: "D01",
    window_start: new Date(now - 901_000).toISOString(),
    window_end: new Date(now - 1_000).toISOString(),
    partial: false,
    counts: { car: 1 },
    avg_speed_kmh: {},
    config_version: "device-v1",
    fw_version: "test",
    produced_at: new Date(now).toISOString(),
  },
  heartbeat: {
    sensor_id: "D01",
    ts: new Date(now).toISOString(),
    uptime_s: 100,
    config_version: "device-v1",
    fw_version: "test",
  },
  daily: {
    schema_version: "1.0",
    sensor_id: "D01",
    day: new Date(now).toISOString().slice(0, 10),
    totals: { car: 1 },
    window_count: 1,
    config_version: "device-v1",
    fw_version: "test",
    produced_at: new Date(now).toISOString(),
  },
};

type Kind = keyof typeof payloads;

async function post(kind: Kind) {
  const { POST } = await {
    counts: () => import("@/app/api/ingest/sensors/[id]/counts/route"),
    heartbeat: () => import("@/app/api/ingest/sensors/[id]/heartbeat/route"),
    daily: () => import("@/app/api/ingest/sensors/[id]/daily/route"),
  }[kind]();
  return POST(new Request(`http://localhost/api/ingest/sensors/D01/${kind}`, {
    method: "POST",
    headers: { "content-type": "application/json", authorization: "Bearer test" },
    body: JSON.stringify(payloads[kind]),
  }), ctx);
}

describe("ingest config version handshake — live mode", () => {
  beforeEach(() => readSensorConfigVersion.mockReset());

  it.each(["counts", "heartbeat", "daily"] as const)(
    "%s advertises the server version after a config bump",
    async (kind) => {
      readSensorConfigVersion.mockResolvedValueOnce("device-v1").mockResolvedValueOnce("server-v2");

      const before = await post(kind);
      expect(before.status).toBe(200);
      expect(await before.json()).toMatchObject({ latest_config_version: "device-v1" });

      const after = await post(kind);
      expect(after.status).toBe(200);
      expect(await after.json()).toMatchObject({ latest_config_version: "server-v2" });
      expect(readSensorConfigVersion).toHaveBeenCalledWith("D01");
    }
  );
});
