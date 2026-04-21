import { describe, expect, it } from "vitest";
import {
  countsPayloadSchema,
  dailyPayloadSchema,
  heartbeatPayloadSchema,
  readingsQuerySchema,
} from "@/lib/schemas";

describe("countsPayloadSchema", () => {
  const valid = {
    schema_version: "1.0",
    sensor_id: "cam-dub-01",
    window_start: "2026-04-21T10:00:00Z",
    window_end: "2026-04-21T10:15:00Z",
    partial: false,
    counts: { person: 68, cyclist: 91 },
    avg_speed_kmh: { person: 4.1 },
    config_version: "abc",
    fw_version: "0.2.0",
    produced_at: "2026-04-21T10:15:00Z",
  };

  it("accepts a complete payload", () => {
    expect(() => countsPayloadSchema.parse(valid)).not.toThrow();
  });

  it("rejects negative counts", () => {
    const bad = { ...valid, counts: { person: -1 } };
    expect(() => countsPayloadSchema.parse(bad)).toThrow();
  });

  it("rejects missing sensor_id", () => {
    const { sensor_id: _omit, ...rest } = valid;
    expect(() => countsPayloadSchema.parse(rest)).toThrow();
  });
});

describe("dailyPayloadSchema", () => {
  it("requires an ISO date string", () => {
    expect(() =>
      dailyPayloadSchema.parse({
        schema_version: "1.0",
        sensor_id: "cam-dub-01",
        day: "21-04-2026", // wrong format
        totals: { person: 1 },
        window_count: 1,
        config_version: "abc",
        fw_version: "0.2.0",
        produced_at: "2026-04-22T00:00:00Z",
      })
    ).toThrow();
  });
});

describe("heartbeatPayloadSchema", () => {
  it("accepts a minimal payload", () => {
    expect(() =>
      heartbeatPayloadSchema.parse({
        sensor_id: "cam-dub-01",
        ts: "2026-04-21T10:20:00Z",
        uptime_s: 100,
        config_version: "abc",
        fw_version: "0.2.0",
      })
    ).not.toThrow();
  });
});

describe("readingsQuerySchema", () => {
  it("defaults metric=counts and bucket=15", () => {
    const q = readingsQuerySchema.parse({});
    expect(q.metric).toBe("counts");
    expect(q.bucket).toBe(15);
  });

  it("rejects invalid metric", () => {
    expect(() => readingsQuerySchema.parse({ metric: "bogus" })).toThrow();
  });
});
