// Fail-closed production gates + timing-safe token compares.
// Covers docs/production_readiness.md findings H6, H7, H8, M3.

import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(() => {
  vi.unstubAllEnvs();
  vi.resetModules();
});

function req(auth?: string): Request {
  return new Request("http://localhost/api/test", {
    headers: auth ? { authorization: auth } : {},
  });
}

describe("data-source — fail closed in production (H7)", () => {
  it("throws in production when CAMINA_DATA_SOURCE is unset", async () => {
    vi.stubEnv("VERCEL_ENV", "production");
    vi.resetModules();
    await expect(import("@/lib/data-source")).rejects.toThrow(
      /CAMINA_DATA_SOURCE/
    );
  });

  it("throws in production on an invalid value", async () => {
    vi.stubEnv("VERCEL_ENV", "production");
    vi.stubEnv("CAMINA_DATA_SOURCE", "staging");
    vi.resetModules();
    await expect(import("@/lib/data-source")).rejects.toThrow(/"staging"/);
  });

  it("honours an explicit live value in production", async () => {
    vi.stubEnv("VERCEL_ENV", "production");
    vi.stubEnv("CAMINA_DATA_SOURCE", "live");
    vi.resetModules();
    const mod = await import("@/lib/data-source");
    expect(mod.dataSource).toBe("live");
  });

  it("defaults to mock outside production", async () => {
    vi.resetModules();
    const mod = await import("@/lib/data-source");
    expect(mod.dataSource).toBe("mock");
  });
});

describe("verifyCron — fail closed in production (M3)", () => {
  it("rejects in production when VERCEL_CRON_SECRET is missing", async () => {
    vi.stubEnv("VERCEL_ENV", "production");
    const { verifyCron } = await import("@/lib/cron-auth");
    expect(verifyCron(req())?.status).toBe(403);
  });

  it("skips the check outside production when the secret is missing", async () => {
    const { verifyCron } = await import("@/lib/cron-auth");
    expect(verifyCron(req())).toBeNull();
  });

  it("accepts the correct bearer token", async () => {
    vi.stubEnv("VERCEL_CRON_SECRET", "cron-secret");
    const { verifyCron } = await import("@/lib/cron-auth");
    expect(verifyCron(req("Bearer cron-secret"))).toBeNull();
  });

  it("rejects a wrong bearer token of a different length", async () => {
    vi.stubEnv("VERCEL_CRON_SECRET", "cron-secret");
    const { verifyCron } = await import("@/lib/cron-auth");
    expect(verifyCron(req("Bearer nope"))?.status).toBe(403);
  });
});

describe("verifyIngestToken — timing-safe dev token (H6)", () => {
  it("accepts the dev token", async () => {
    vi.stubEnv("CAMINA_DEV_INGEST_TOKEN", "dev-token");
    vi.resetModules();
    const { verifyIngestToken } = await import("@/lib/ingest-auth");
    expect(verifyIngestToken(req("Bearer dev-token"), "D01")).toBeNull();
  });

  it("rejects a wrong token of a different length", async () => {
    vi.stubEnv("CAMINA_DEV_INGEST_TOKEN", "dev-token");
    vi.resetModules();
    const { verifyIngestToken } = await import("@/lib/ingest-auth");
    expect(verifyIngestToken(req("Bearer nope"), "D01")?.status).toBe(401);
  });

  it("rejects a missing token", async () => {
    vi.stubEnv("CAMINA_DEV_INGEST_TOKEN", "dev-token");
    vi.resetModules();
    const { verifyIngestToken } = await import("@/lib/ingest-auth");
    expect(verifyIngestToken(req(), "D01")?.status).toBe(401);
  });
});

describe("secureCompare", () => {
  it("matches equal strings and rejects different ones", async () => {
    const { secureCompare } = await import("@/lib/secure-compare");
    expect(secureCompare("token-a", "token-a")).toBe(true);
    expect(secureCompare("token-a", "token-b")).toBe(false);
  });

  it("handles unequal lengths without throwing", async () => {
    const { secureCompare } = await import("@/lib/secure-compare");
    expect(secureCompare("short", "a-much-longer-secret")).toBe(false);
  });
});
