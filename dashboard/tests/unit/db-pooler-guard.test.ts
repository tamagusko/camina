// The Neon pooled-endpoint guard checks the hostname, and only on a deployed
// Vercel function (a local `next start` also runs NODE_ENV=production).

import { describe, expect, it } from "vitest";
import { pooledUrlError } from "@/lib/db";

const POOLED = "postgres://u:p@ep-cool-name-123456-pooler.eu-central-1.aws.neon.tech/camina";
const DIRECT = "postgres://u:p@ep-cool-name-123456.eu-central-1.aws.neon.tech/camina";

describe("pooledUrlError", () => {
  it("accepts the pooled host on Vercel production", () => {
    expect(pooledUrlError(POOLED, "production")).toBeNull();
  });

  it("rejects the direct host on Vercel production", () => {
    expect(pooledUrlError(DIRECT, "production")).toMatch(/pooled endpoint/);
  });

  it("is not fooled by '-pooler' outside the hostname", () => {
    expect(pooledUrlError(`${DIRECT}?application_name=x-pooler`, "production")).toMatch(/pooled/);
    expect(pooledUrlError("postgres://u-pooler:p@ep-x.neon.tech/db", "production")).toMatch(/pooled/);
  });

  it("rejects an unparsable URL on Vercel production", () => {
    expect(pooledUrlError("not a url", "production")).toMatch(/pooled/);
  });

  it("applies to previews too", () => {
    expect(pooledUrlError(DIRECT, "preview")).toMatch(/pooled/);
  });

  it("does not apply off Vercel (local next start, vercel dev)", () => {
    expect(pooledUrlError("postgres://camina:camina@127.0.0.1:55432/camina", undefined)).toBeNull();
    expect(pooledUrlError(DIRECT, "development")).toBeNull();
  });
});
