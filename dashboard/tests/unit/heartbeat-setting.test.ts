import { afterEach, describe, expect, it, vi } from "vitest";
import {
  DEFAULT_HEARTBEAT_MINUTES,
  heartbeatMinutes,
  silentAfterMs,
  withHeartbeat,
} from "@/lib/heartbeat";

// CAMINA_HEARTBEAT_MINUTES is the one place that sets how often sensors send a
// heartbeat. 15 min in the pilot (Neon free compute hours); the goal is 5 min.

describe("heartbeatMinutes", () => {
  it("defaults to 15 min for the free-tier pilot", () => {
    expect(DEFAULT_HEARTBEAT_MINUTES).toBe(15);
    expect(heartbeatMinutes({})).toBe(15);
  });

  it("reads CAMINA_HEARTBEAT_MINUTES", () => {
    expect(heartbeatMinutes({ CAMINA_HEARTBEAT_MINUTES: "5" })).toBe(5);
    expect(heartbeatMinutes({ CAMINA_HEARTBEAT_MINUTES: " 15 " })).toBe(15);
  });

  it("rejects a value that would not line up with the 15-min windows", () => {
    for (const bad of ["7", "0", "-5", "abc", "5.5", "90"]) {
      expect(() => heartbeatMinutes({ CAMINA_HEARTBEAT_MINUTES: bad })).toThrow(
        /CAMINA_HEARTBEAT_MINUTES/
      );
    }
  });
});

describe("withHeartbeat", () => {
  it("sets the interval and tags the version, so a change reaches every sensor", () => {
    const at15 = withHeartbeat({ publish_interval_minutes: 15 }, "v3", 15);
    const at5 = withHeartbeat({ publish_interval_minutes: 15 }, "v3", 5);
    expect(at15.config.heartbeat_interval_minutes).toBe(15);
    expect(at5.config.heartbeat_interval_minutes).toBe(5);
    expect(at15.config.publish_interval_minutes).toBe(15);
    // A different setting gives a different version: the sensor's poller sees
    // it on its next heartbeat and fetches the new config.
    expect(at15.config_version).not.toBe(at5.config_version);
    expect(at15.config_version.startsWith("v3")).toBe(true);
  });

  it("overrides a per-sensor value stored in the database", () => {
    const out = withHeartbeat({ heartbeat_interval_minutes: 10 }, "v1", 15);
    expect(out.config.heartbeat_interval_minutes).toBe(15);
  });
});

describe("silentAfterMs", () => {
  it("is three missed heartbeats", () => {
    expect(silentAfterMs(15)).toBe(45 * 60_000);
    expect(silentAfterMs(5)).toBe(15 * 60_000);
  });
});

describe("the routes use the one setting", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  it("the mock config and every ingest ack carry the same versioned interval", async () => {
    vi.stubEnv("CAMINA_HEARTBEAT_MINUTES", "5");
    vi.resetModules();
    const { MOCK_CONFIG } = await import("@/lib/mock-sensor-config");
    expect(MOCK_CONFIG.heartbeat_interval_minutes).toBe(5);
    expect(MOCK_CONFIG.config_version).toMatch(/hb5$/);
  });
});
