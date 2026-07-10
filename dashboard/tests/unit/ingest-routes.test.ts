// Ingest route-handler + persistence-logic tests.
// Covers docs/production_readiness.md findings H2, H5, H6, M17.

import { afterEach, describe, expect, it, vi } from "vitest";

const DEV_TOKEN = "dev-token";

interface CountsBody {
  schema_version: string;
  sensor_id: string;
  window_start: string;
  window_end: string;
  partial: boolean;
  counts: Record<string, number>;
  avg_speed_kmh: Record<string, number>;
  config_version: string;
  fw_version: string;
  produced_at: string;
}

function countsBody(overrides: Partial<CountsBody> = {}): CountsBody {
  const now = Date.now();
  return {
    schema_version: "1",
    sensor_id: "D01",
    window_start: new Date(now - 901_000).toISOString(),
    window_end: new Date(now - 1_000).toISOString(),
    partial: false,
    counts: { car: 3, person: 1 },
    avg_speed_kmh: { car: 22.5 },
    config_version: "cfg-1",
    fw_version: "fw-1",
    produced_at: new Date(now - 1_000).toISOString(),
    ...overrides,
  };
}

function postRequest(body: unknown, token?: string): Request {
  return new Request("http://localhost/api/ingest/sensors/D01/counts", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      ...(token ? { authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
  });
}

const ctx = { params: Promise.resolve({ id: "D01" }) };

afterEach(() => {
  vi.unstubAllEnvs();
  vi.resetModules();
});

describe("POST /api/ingest/sensors/[id]/counts — mock mode", () => {
  it("accepts a valid payload with the dev token (2xx)", async () => {
    vi.stubEnv("CAMINA_DEV_INGEST_TOKEN", DEV_TOKEN);
    vi.resetModules();
    const { POST } = await import(
      "@/app/api/ingest/sensors/[id]/counts/route"
    );
    const res = await POST(postRequest(countsBody(), DEV_TOKEN), ctx);
    expect(res.status).toBe(200);
    expect(await res.json()).toMatchObject({ ok: true });
  });

  it("rejects a missing/bad token (401)", async () => {
    vi.stubEnv("CAMINA_DEV_INGEST_TOKEN", DEV_TOKEN);
    vi.resetModules();
    const { POST } = await import(
      "@/app/api/ingest/sensors/[id]/counts/route"
    );
    const res = await POST(postRequest(countsBody()), ctx);
    expect(res.status).toBe(401);
  });

  it("rejects a malformed payload (400)", async () => {
    vi.stubEnv("CAMINA_DEV_INGEST_TOKEN", DEV_TOKEN);
    vi.resetModules();
    const { POST } = await import(
      "@/app/api/ingest/sensors/[id]/counts/route"
    );
    const res = await POST(postRequest({ nope: true }, DEV_TOKEN), ctx);
    expect(res.status).toBe(400);
  });

  it("rejects a window_end more than 60 s in the future (422)", async () => {
    vi.stubEnv("CAMINA_DEV_INGEST_TOKEN", DEV_TOKEN);
    vi.resetModules();
    const { POST } = await import(
      "@/app/api/ingest/sensors/[id]/counts/route"
    );
    const now = Date.now();
    const body = countsBody({
      window_start: new Date(now + 240_000).toISOString(),
      window_end: new Date(now + 300_000).toISOString(), // +5 min
    });
    const res = await POST(postRequest(body, DEV_TOKEN), ctx);
    expect(res.status).toBe(422);
    expect(await res.json()).toMatchObject({ error: "timestamp_in_future" });
  });

  it("rejects a payload whose sensor_id disagrees with the path (400)", async () => {
    vi.stubEnv("CAMINA_DEV_INGEST_TOKEN", DEV_TOKEN);
    vi.resetModules();
    const { POST } = await import(
      "@/app/api/ingest/sensors/[id]/counts/route"
    );
    const res = await POST(
      postRequest(countsBody({ sensor_id: "D99" }), DEV_TOKEN),
      ctx
    );
    expect(res.status).toBe(400);
  });
});

describe("verifyIngestToken — per-sensor lookup (H6)", () => {
  it("returns 403 when the token belongs to a different sensor", async () => {
    vi.stubEnv("CAMINA_DATA_SOURCE", "live");
    vi.resetModules();
    const { verifyIngestToken } = await import("@/lib/ingest-auth");
    const deps = {
      getSensorTokenHash: async () => null,
      findSensorIdByTokenHash: async () => "D02",
    };
    const req = new Request("http://localhost", {
      headers: { authorization: "Bearer some-other-sensor-token" },
    });
    const res = await verifyIngestToken(req, "D01", deps);
    expect(res?.status).toBe(403);
  });

  it("returns 401 when the token matches no sensor", async () => {
    vi.stubEnv("CAMINA_DATA_SOURCE", "live");
    vi.resetModules();
    const { verifyIngestToken } = await import("@/lib/ingest-auth");
    const deps = {
      getSensorTokenHash: async () => null,
      findSensorIdByTokenHash: async () => null,
    };
    const req = new Request("http://localhost", {
      headers: { authorization: "Bearer nonsense" },
    });
    const res = await verifyIngestToken(req, "D01", deps);
    expect(res?.status).toBe(401);
  });

  it("accepts the token whose SHA-256 matches the stored hash", async () => {
    vi.stubEnv("CAMINA_DATA_SOURCE", "live");
    vi.resetModules();
    const { createHash } = await import("node:crypto");
    const { verifyIngestToken } = await import("@/lib/ingest-auth");
    const token = "the-real-token";
    const hash = createHash("sha256").update(token).digest("hex");
    const deps = {
      getSensorTokenHash: async () => hash,
      findSensorIdByTokenHash: async () => "D01",
    };
    const req = new Request("http://localhost", {
      headers: { authorization: `Bearer ${token}` },
    });
    expect(await verifyIngestToken(req, "D01", deps)).toBeNull();
  });
});

describe("ingest-store — pure upsert/skew logic (H2/H5)", () => {
  it("fans a counts payload out to one row per reported class", async () => {
    const { buildCountsRows } = await import("@/lib/ingest-store");
    const rows = buildCountsRows(countsBody(), "D01");
    expect(rows).toHaveLength(2);
    const car = rows.find((r) => r.className === "car");
    expect(car).toMatchObject({ sensorId: "D01", count: 3, avgSpeedKmh: 22.5 });
    // Class present in counts but absent from avg_speed_kmh → null speed.
    const person = rows.find((r) => r.className === "person");
    expect(person?.avgSpeedKmh).toBeNull();
  });

  it("enforces the partial-promotion rule", async () => {
    const { shouldOverwrite } = await import("@/lib/ingest-store");
    // Only the final←partial demotion is blocked.
    expect(shouldOverwrite(false, true)).toBe(false);
    expect(shouldOverwrite(false, false)).toBe(true);
    expect(shouldOverwrite(true, true)).toBe(true);
    expect(shouldOverwrite(true, false)).toBe(true);
  });

  it("checks timestamp skew: 60 s future / 7 day past bounds", async () => {
    const { checkTimestampSkew } = await import("@/lib/ingest-store");
    const now = Date.now();
    expect(checkTimestampSkew(new Date(now).toISOString(), now)).toBeNull();
    expect(
      checkTimestampSkew(new Date(now + 120_000).toISOString(), now)?.error
    ).toBe("timestamp_in_future");
    expect(
      checkTimestampSkew(
        new Date(now - 8 * 24 * 3600_000).toISOString(),
        now
      )?.error
    ).toBe("timestamp_too_old");
    expect(checkTimestampSkew("not-a-date", now)?.error).toBe(
      "invalid_timestamp"
    );
  });

  it("builds a single conflict-guarded upsert statement", async () => {
    const { persistCounts } = await import("@/lib/ingest-store");
    const captured: {
      rows?: unknown[];
      conflict?: { target?: unknown[]; setWhere?: unknown };
    } = {};
    const chain = {
      values(rows: unknown[]) {
        captured.rows = rows;
        return chain;
      },
      onConflictDoUpdate(cfg: { target?: unknown[]; setWhere?: unknown }) {
        captured.conflict = cfg;
        return Promise.resolve();
      },
    };
    const fakeDb = { insert: () => chain };
    await persistCounts(
      countsBody(),
      "D01",
      fakeDb as unknown as Parameters<typeof persistCounts>[2]
    );
    expect(captured.rows).toHaveLength(2);
    expect(captured.conflict?.target).toHaveLength(3);
    // Promotion rule enforced in SQL via setWhere.
    expect(captured.conflict?.setWhere).toBeTruthy();
  });
});
