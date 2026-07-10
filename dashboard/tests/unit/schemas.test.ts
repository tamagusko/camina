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

  it("accepts an edge-shaped payload (pydantic model_dump_json wire format)", () => {
    // Mirrors src/camina/io/schemas.py CountsPayload serialization.
    const edge = {
      schema_version: "1.0",
      sensor_id: "s",
      window_start: "2026-01-01T00:00:00Z",
      window_end: "2026-01-01T00:15:00Z",
      partial: false,
      counts: {},
      avg_speed_kmh: {},
      config_version: "c",
      fw_version: "f",
      produced_at: "2026-01-01T00:15:19.886602Z",
    };
    expect(() => countsPayloadSchema.parse(edge)).not.toThrow();
  });

  it("rejects negative counts", () => {
    const bad = { ...valid, counts: { person: -1 } };
    expect(() => countsPayloadSchema.parse(bad)).toThrow();
  });

  it("rejects unknown class keys in counts", () => {
    const bad = { ...valid, counts: { ...valid.counts, unicycle: 1 } };
    expect(() => countsPayloadSchema.parse(bad)).toThrow();
  });

  it("rejects counts above 65535", () => {
    const bad = { ...valid, counts: { person: 65536 } };
    expect(() => countsPayloadSchema.parse(bad)).toThrow();
  });

  it("rejects window_end <= window_start", () => {
    const bad = { ...valid, window_end: valid.window_start };
    expect(() => countsPayloadSchema.parse(bad)).toThrow();
  });

  it("rejects windows longer than 3600 s", () => {
    const bad = { ...valid, window_end: "2026-04-21T11:00:01Z" };
    expect(() => countsPayloadSchema.parse(bad)).toThrow();
  });

  it("rejects windows more than 24 h in the future", () => {
    const start = new Date(Date.now() + 25 * 60 * 60 * 1000);
    const end = new Date(start.getTime() + 15 * 60 * 1000);
    const bad = {
      ...valid,
      window_start: start.toISOString(),
      window_end: end.toISOString(),
    };
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
  const minimal = {
    sensor_id: "cam-dub-01",
    ts: "2026-04-21T10:20:00Z",
    uptime_s: 100,
    config_version: "abc",
    fw_version: "0.2.0",
  };

  it("accepts a minimal payload", () => {
    expect(() => heartbeatPayloadSchema.parse(minimal)).not.toThrow();
  });

  it("rejects unknown keys (strict)", () => {
    const bad = { ...minimal, debug_field: true };
    expect(() => heartbeatPayloadSchema.parse(bad)).toThrow();
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
