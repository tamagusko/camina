import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import {
  countsPayloadSchema,
  dailyPayloadSchema,
  heartbeatPayloadSchema,
} from "@/lib/schemas";

type PayloadLine = {
  endpoint: "counts" | "daily" | "heartbeat";
  sent_at: string;
  body: Record<string, unknown>;
};

const fixturePath = resolve(process.cwd(), "../tests/fixtures/payloads/one_day.jsonl");
const payloads = readFileSync(fixturePath, "utf8")
  .trim()
  .split("\n")
  .map((line) => JSON.parse(line) as PayloadLine);

describe("edge payload contract fixture", () => {
  it("validates every generated request body against the dashboard schema", () => {
    expect(payloads.length).toBeGreaterThan(0);
    for (const payload of payloads) {
      const parsed = {
        counts: countsPayloadSchema,
        daily: dailyPayloadSchema,
        heartbeat: heartbeatPayloadSchema,
      }[payload.endpoint].safeParse(payload.body);
      expect(parsed.success, `${payload.endpoint} at ${payload.sent_at}`).toBe(true);
    }
  });
});
