// SCRATCH-ONLY audit test (not in repo): feeds real edge-generated request bodies
// (captured from src/camina/io/https_publisher.py via httpx.MockTransport) and a
// real Python-packed LoRa frame through the dashboard zod schemas + route handlers.
import { readFileSync } from "node:fs";
import path from "node:path";
import { afterEach, describe, expect, it, vi } from "vitest";

const OUT = path.resolve(__dirname, "../../../e2e_out");
const captured = JSON.parse(readFileSync(path.join(OUT, "captured_requests.json"), "utf-8")) as {
  path: string; method: string; body?: Record<string, unknown>;
}[];
const lora = JSON.parse(readFileSync(path.join(OUT, "lora_frame.json"), "utf-8")) as {
  b64: string; epoch: number; counts: Record<string, number>;
};

function freshen(body: Record<string, unknown>): Record<string, unknown> {
  // Captured windows are real wall-clock; re-anchor to now so skew checks don't
  // mask schema results. Keeps the exact serialization format of the edge.
  const b = { ...body };
  const now = Date.now();
  const iso = (ms: number) => new Date(ms).toISOString().replace(".000Z", "Z");
  if ("window_start" in b) { b.window_start = iso(now - 901_000); b.window_end = iso(now - 1_000); }
  if ("produced_at" in b) b.produced_at = iso(now - 1_000);
  if ("ts" in b) b.ts = iso(now - 1_000);
  if ("last_window_end" in b) b.last_window_end = iso(now - 1_000);
  return b;
}

afterEach(() => { vi.unstubAllEnvs(); vi.resetModules(); });

describe("edge -> dashboard contract (audit)", () => {
  const pick = (suffix: string) => captured.find((c) => c.method === "POST" && c.path.endsWith(suffix))!;

  it("edge counts body raw serialization passes countsPayloadSchema", async () => {
    const { countsPayloadSchema } = await import("@/lib/schemas");
    const raw = pick("/counts").body!;
    const r = countsPayloadSchema.safeParse(raw);
    console.log("RAW counts body:", JSON.stringify(raw), "parse:", r.success, r.success ? "" : JSON.stringify(r.error.issues));
    expect(r.success).toBe(true);
  });

  it("edge daily body passes dailyPayloadSchema", async () => {
    const { dailyPayloadSchema } = await import("@/lib/schemas");
    const r = dailyPayloadSchema.safeParse(pick("/daily").body!);
    console.log("daily parse:", r.success, r.success ? "" : JSON.stringify(r.error.issues));
    expect(r.success).toBe(true);
  });

  it("edge heartbeat body passes heartbeatPayloadSchema", async () => {
    const { heartbeatPayloadSchema } = await import("@/lib/schemas");
    const r = heartbeatPayloadSchema.safeParse(pick("/heartbeat").body!);
    console.log("heartbeat parse:", r.success, r.success ? "" : JSON.stringify(r.error.issues));
    expect(r.success).toBe(true);
  });

  for (const kind of ["counts", "daily", "heartbeat"] as const) {
    it(`route handler ${kind} (mock mode, dev token) accepts re-anchored edge body`, async () => {
      vi.stubEnv("CAMINA_DEV_INGEST_TOKEN", "dev-token");
      vi.stubEnv("CAMINA_DATA_SOURCE", "mock");
      vi.resetModules();
      const mod = await import(`@/app/api/ingest/sensors/[id]/${kind}/route`);
      const c = pick(`/${kind}`);
      const id = c.path.split("/")[4];
      const req = new Request(`http://localhost${c.path}`, {
        method: "POST",
        headers: { "content-type": "application/json", authorization: "Bearer dev-token" },
        body: JSON.stringify(freshen(c.body!)),
      });
      const res = await mod.POST(req, { params: Promise.resolve({ id }) });
      const json = await res.json();
      console.log(`${kind} route ->`, res.status, JSON.stringify(json).slice(0, 300));
      expect(res.status).toBe(200);
    });
  }

  it("config route mock payload validates against edge SensorConfig field set", async () => {
    vi.stubEnv("CAMINA_DEV_INGEST_TOKEN", "dev-token");
    vi.stubEnv("CAMINA_DATA_SOURCE", "mock");
    vi.resetModules();
    const mod = await import("@/app/api/ingest/sensors/[id]/config/route");
    const res = await mod.GET(new Request("http://localhost/api/ingest/sensors/cam-dub-01/config", {
      headers: { authorization: "Bearer dev-token" },
    }), { params: Promise.resolve({ id: "cam-dub-01" }) });
    const json = await res.json();
    console.log("config route ->", res.status, JSON.stringify(json));
    const edgeFields = ["config_version", "publish_interval_minutes", "heartbeat_interval_minutes", "daily_publish_time_utc", "detection_zone", "frame_skip", "min_track_hits"].sort();
    expect(Object.keys(json).sort()).toEqual(edgeFields);
  });

  it("Python-packed LoRa frame decodes identically in TS", async () => {
    const { decodeLoraPayload } = await import("@/lib/lora-codec");
    const d = decodeLoraPayload(lora.b64);
    console.log("lora decode:", JSON.stringify(d));
    expect(d.cameraId).toBe("D01");
    expect(Date.parse(d.windowStart) / 1000).toBe(lora.epoch);
    for (const [k, v] of Object.entries(lora.counts)) expect(d.counts[k as keyof typeof d.counts]).toBe(v);
  });
});
