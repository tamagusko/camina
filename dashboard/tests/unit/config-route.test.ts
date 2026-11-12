import { beforeEach, describe, expect, it, vi } from "vitest";

const readSensorConfig = vi.fn();

vi.mock("@/lib/data-source", () => ({ isMock: false }));
vi.mock("@/lib/ingest-auth", () => ({
  verifyIngestToken: vi.fn().mockResolvedValue(null),
}));
vi.mock("@/lib/ingest-ratelimit", () => ({
  checkIngestRateLimit: vi.fn().mockResolvedValue(null),
}));
vi.mock("@/lib/ingest-store", () => ({ readSensorConfig }));

const request = new Request("http://localhost/api/ingest/sensors/D01/config", {
  headers: { authorization: "Bearer test" },
});
const ctx = { params: Promise.resolve({ id: "D01" }) };

describe("GET /api/ingest/sensors/[id]/config — live mode", () => {
  beforeEach(() => readSensorConfig.mockReset());

  it("returns the server config with sensors.config_version", async () => {
    readSensorConfig.mockResolvedValue({
      config_version: "server-v2",
      config: {
        config_version: "stale-json-version",
        publish_interval_minutes: 15,
        heartbeat_interval_minutes: 5,
        daily_publish_time_utc: "00:00",
        detection_zone: null,
        frame_skip: 5,
        min_track_hits: 3,
      },
    });
    const { GET } = await import(
      "@/app/api/ingest/sensors/[id]/config/route"
    );
    const response = await GET(request, ctx);
    expect(response.status).toBe(200);
    expect(await response.json()).toMatchObject({
      config_version: "server-v2",
      publish_interval_minutes: 15,
    });
  });

  it("returns 404 for an unknown sensor", async () => {
    readSensorConfig.mockResolvedValue(null);
    const { GET } = await import(
      "@/app/api/ingest/sensors/[id]/config/route"
    );
    const response = await GET(request, ctx);
    expect(response.status).toBe(404);
  });

  it("rejects an invalid stored config at the response boundary", async () => {
    readSensorConfig.mockResolvedValue({
      config_version: "server-v2",
      config: { publish_interval_minutes: 0 },
    });
    const { GET } = await import(
      "@/app/api/ingest/sensors/[id]/config/route"
    );
    const response = await GET(request, ctx);
    expect(response.status).toBe(500);
    expect(await response.json()).toEqual({ error: "invalid_sensor_config" });
  });
});
