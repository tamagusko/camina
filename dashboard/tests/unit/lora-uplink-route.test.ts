// TTN LoRaWAN uplink webhook route tests.
// Follows the ingest-routes.test.ts style: stub env, resetModules, dynamic
// import so data-source / auth resolve against the stubbed environment.

import { afterEach, describe, expect, it, vi } from "vitest";
import { ROAD_USER_CLASSES } from "@/lib/types";

const WEBHOOK_KEY = "ttn-shared-secret";
const EPOCH = Math.floor(Date.now() / 1000);
const WIDE = new Set(["person", "cyclist", "car"]);

function buildFrame(
  cameraId: string,
  epochSeconds: number,
  counts: Partial<Record<string, number>> = {},
  schemaVersion = 2
): Buffer {
  const buf = Buffer.alloc(20);
  buf.write(cameraId, 0, 3, "ascii");
  buf.writeUInt32BE(epochSeconds, 3);
  let off = 7;
  for (const cls of ROAD_USER_CLASSES) {
    const v = counts[cls] ?? 0;
    if (WIDE.has(cls)) {
      buf.writeUInt16BE(v, off);
      off += 2;
    } else {
      buf.writeUInt8(v, off);
      off += 1;
    }
  }
  buf.writeUInt8(schemaVersion, 19);
  return buf;
}

function uplinkBody(frmPayload: string) {
  return {
    end_device_ids: { device_id: "d01" },
    uplink_message: { frm_payload: frmPayload },
    received_at: new Date(EPOCH * 1000).toISOString(),
  };
}

function postRequest(body: unknown, key?: string): Request {
  return new Request("http://localhost/api/ingest/lora/uplink", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      ...(key ? { "x-camina-webhook-key": key } : {}),
    },
    body: JSON.stringify(body),
  });
}

afterEach(() => {
  vi.unstubAllEnvs();
  vi.resetModules();
});

async function loadPost() {
  const mod = await import("@/app/api/ingest/lora/uplink/route");
  return mod.POST;
}

describe("POST /api/ingest/lora/uplink — mock mode", () => {
  it("accepts a valid uplink with the correct webhook key (202)", async () => {
    vi.stubEnv("TTN_WEBHOOK_KEY", WEBHOOK_KEY);
    vi.resetModules();
    const POST = await loadPost();
    const frame = buildFrame("D01", EPOCH, { person: 425, car: 12 }).toString(
      "base64"
    );
    const res = await POST(postRequest(uplinkBody(frame), WEBHOOK_KEY));
    expect(res.status).toBe(202);
    expect(await res.json()).toMatchObject({
      ok: true,
      source: "lora",
      sensor_id: "D01",
    });
  });

  it("rejects a wrong webhook key (403)", async () => {
    vi.stubEnv("TTN_WEBHOOK_KEY", WEBHOOK_KEY);
    vi.resetModules();
    const POST = await loadPost();
    const frame = buildFrame("D01", EPOCH, {}).toString("base64");
    const res = await POST(postRequest(uplinkBody(frame), "wrong-key"));
    expect(res.status).toBe(403);
  });

  it("rejects a missing webhook key when the secret is set (403)", async () => {
    vi.stubEnv("TTN_WEBHOOK_KEY", WEBHOOK_KEY);
    vi.resetModules();
    const POST = await loadPost();
    const frame = buildFrame("D01", EPOCH, {}).toString("base64");
    const res = await POST(postRequest(uplinkBody(frame))); // no header
    expect(res.status).toBe(403);
  });

  it("rejects a malformed TTN envelope (400)", async () => {
    vi.stubEnv("TTN_WEBHOOK_KEY", WEBHOOK_KEY);
    vi.resetModules();
    const POST = await loadPost();
    const res = await POST(postRequest({ nope: true }, WEBHOOK_KEY));
    expect(res.status).toBe(400);
    expect(await res.json()).toMatchObject({ error: "bad_uplink" });
  });

  it("rejects a bad payload — wrong schema version (400)", async () => {
    vi.stubEnv("TTN_WEBHOOK_KEY", WEBHOOK_KEY);
    vi.resetModules();
    const POST = await loadPost();
    const frame = buildFrame("D01", EPOCH, {}, 1).toString("base64");
    const res = await POST(postRequest(uplinkBody(frame), WEBHOOK_KEY));
    expect(res.status).toBe(400);
    expect(await res.json()).toMatchObject({ error: "bad_payload" });
  });

  it("rejects a wrong-length frame (400)", async () => {
    vi.stubEnv("TTN_WEBHOOK_KEY", WEBHOOK_KEY);
    vi.resetModules();
    const POST = await loadPost();
    // Truncate a valid 20-byte frame to 18 bytes.
    const frame = buildFrame("D01", EPOCH, {})
      .subarray(0, 18)
      .toString("base64");
    const res = await POST(postRequest(uplinkBody(frame), WEBHOOK_KEY));
    expect(res.status).toBe(400);
    expect(await res.json()).toMatchObject({ error: "bad_payload" });
  });
});

describe("verifyWebhookKey — fail-closed idiom", () => {
  it("skips the check in dev when the secret is unset", async () => {
    // TTN_WEBHOOK_KEY unset, NODE_ENV=test (not production) → dev skip.
    vi.resetModules();
    const { verifyWebhookKey } = await import(
      "@/app/api/ingest/lora/uplink/route"
    );
    const req = new Request("http://localhost", { method: "POST" });
    expect(verifyWebhookKey(req)).toBeNull();
  });

  it("fails closed in production when the secret is unset (403)", async () => {
    // CAMINA_DATA_SOURCE must be set or data-source throws at import in prod.
    vi.stubEnv("VERCEL_ENV", "production");
    vi.stubEnv("CAMINA_DATA_SOURCE", "mock");
    vi.resetModules();
    const { verifyWebhookKey } = await import(
      "@/app/api/ingest/lora/uplink/route"
    );
    const req = new Request("http://localhost", { method: "POST" });
    expect(verifyWebhookKey(req)?.status).toBe(403);
  });
});
