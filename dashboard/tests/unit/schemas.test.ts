import { describe, expect, it } from "vitest";
import {
  countsPayloadSchema,
  dailyPayloadSchema,
  heartbeatPayloadSchema,
  readingsQuerySchema,
  sensorConfigResponseSchema,
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
    // Mirrors camina/io/schemas.py CountsPayload serialization.
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

  it("accepts directional counts when they sum to the published total", () => {
    const directional = {
      ...valid,
      schema_version: "1.1",
      counts: { car: 5 },
      counts_by_direction: { AB: { car: 2 }, BA: { car: 3 } },
    };
    expect(() => countsPayloadSchema.parse(directional)).not.toThrow();
  });

  it("rejects invalid direction keys and directional sum mismatches", () => {
    expect(() =>
      countsPayloadSchema.parse({
        ...valid,
        counts_by_direction: { AB: { car: 2 }, CA: { car: 1 } },
      })
    ).toThrow();
    expect(() =>
      countsPayloadSchema.parse({
        ...valid,
        counts: { car: 5 },
        counts_by_direction: { AB: { car: 5 } },
      })
    ).toThrow();
    expect(() =>
      countsPayloadSchema.parse({
        ...valid,
        counts: { car: 5 },
        counts_by_direction: { AB: { car: 1 } },
      })
    ).toThrow();
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

  it("accepts schema 1.1 direction counts whose cells sum to each class total", () => {
    const directional = {
      ...valid,
      schema_version: "1.1",
      counts_by_direction: {
        AB: { person: 40, cyclist: 91 },
        BA: { person: 28 },
      },
    };
    expect(() => countsPayloadSchema.parse(directional)).not.toThrow();
  });

  it("rejects unknown direction and class keys", () => {
    expect(() =>
      countsPayloadSchema.parse({
        ...valid,
        schema_version: "1.1",
        counts_by_direction: { north: { person: 68 } },
      })
    ).toThrow();
    expect(() =>
      countsPayloadSchema.parse({
        ...valid,
        schema_version: "1.1",
        counts_by_direction: { AB: { unicycle: 68 } },
      })
    ).toThrow();
  });

  it("rejects direction cells outside the count bounds", () => {
    expect(() =>
      countsPayloadSchema.parse({
        ...valid,
        schema_version: "1.1",
        counts_by_direction: { AB: { person: 65536 } },
      })
    ).toThrow();
  });

  it("rejects direction totals that do not equal counts", () => {
    expect(() =>
      countsPayloadSchema.parse({
        ...valid,
        schema_version: "1.1",
        counts_by_direction: { AB: { person: 40 }, BA: { person: 27 } },
      })
    ).toThrow();
  });

  it("requires schema 1.1 when direction is present and 1.0 when absent", () => {
    expect(() =>
      countsPayloadSchema.parse({
        ...valid,
        counts_by_direction: { AB: { person: 68, cyclist: 91 } },
      })
    ).toThrow();
    expect(() =>
      countsPayloadSchema.parse({ ...valid, schema_version: "1.1" })
    ).toThrow();
  });
});

describe("sensorConfigResponseSchema", () => {
  const config = {
    config_version: "cfg-2",
    publish_interval_minutes: 15,
    heartbeat_interval_minutes: 5,
    daily_publish_time_utc: "00:00",
    detection_zone: null,
    frame_skip: 5,
    min_track_hits: 3,
  };

  it("accepts the config response consumed by the edge poller", () => {
    expect(sensorConfigResponseSchema.parse(config)).toEqual(config);
  });

  it("applies the edge schema defaults", () => {
    const { daily_publish_time_utc: _time, detection_zone: _zone, ...minimal } =
      config;
    expect(sensorConfigResponseSchema.parse(minimal)).toMatchObject({
      daily_publish_time_utc: "00:00",
      detection_zone: null,
    });
  });

  it("rejects invalid or unknown config fields", () => {
    expect(() =>
      sensorConfigResponseSchema.parse({ ...config, frame_skip: 0 })
    ).toThrow();
    expect(() =>
      sensorConfigResponseSchema.parse({ ...config, debug: true })
    ).toThrow();
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

  it("accepts outbox telemetry and rejects negative values", () => {
    expect(() =>
      heartbeatPayloadSchema.parse({ ...minimal, outbox_depth: 12, outbox_dropped_total: 3 })
    ).not.toThrow();
    expect(() => heartbeatPayloadSchema.parse({ ...minimal, outbox_depth: -1 })).toThrow();
    expect(() => heartbeatPayloadSchema.parse({ ...minimal, outbox_dropped_total: -1 })).toThrow();
    expect(() => heartbeatPayloadSchema.parse({ ...minimal, outbox_depth: 1.5 })).toThrow();
  });

  it("accepts optional Pi hardware telemetry", () => {
    expect(() =>
      heartbeatPayloadSchema.parse({ ...minimal, throttled: 0x50000, rss_mb: 128.25 })
    ).not.toThrow();
    expect(() =>
      heartbeatPayloadSchema.parse({ ...minimal, throttled: null, rss_mb: null })
    ).not.toThrow();
    expect(() => heartbeatPayloadSchema.parse({ ...minimal, throttled: -1 })).toThrow();
    expect(() => heartbeatPayloadSchema.parse({ ...minimal, rss_mb: -0.1 })).toThrow();
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
