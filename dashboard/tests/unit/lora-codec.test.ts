// Decoder tests for the Phase-4 LoRaWAN binary frame (@/lib/lora-codec).
// Mirrors tests/test_lora_codec.py on the TypeScript side.

import { describe, expect, it } from "vitest";
import { ROAD_USER_CLASSES } from "@/lib/types";
import {
  decodeLoraPayload,
  LoraDecodeError,
  LORA_FRAME_BYTES,
  LORA_SCHEMA_VERSION,
} from "@/lib/lora-codec";

const WIDE = new Set(["person", "cyclist", "car"]);

/** Build a 20-byte frame the way the Python `pack` does, for decode tests. */
function buildFrame(
  cameraId: string,
  epochSeconds: number,
  counts: Partial<Record<string, number>> = {},
  schemaVersion = LORA_SCHEMA_VERSION
): Buffer {
  const buf = Buffer.alloc(LORA_FRAME_BYTES);
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

function b64(...args: Parameters<typeof buildFrame>): string {
  return buildFrame(...args).toString("base64");
}

const EPOCH = 1_776_000_000; // UTC, inside uint32

describe("decodeLoraPayload", () => {
  it("decodes a valid 20-byte frame into the nine-class record", () => {
    const counts = {
      person: 425,
      cyclist: 259,
      car: 310,
      "e-scooter": 40,
      SUV: 22,
      motorcyclist: 6,
      bus: 8,
      delivery_van: 12,
      truck: 4,
    };
    const decoded = decodeLoraPayload(b64("D01", EPOCH, counts));
    expect(decoded.cameraId).toBe("D01");
    expect(decoded.schemaVersion).toBe(LORA_SCHEMA_VERSION);
    expect(decoded.windowStart).toBe(new Date(EPOCH * 1000).toISOString());
    expect(decoded.counts).toEqual(counts);
  });

  it("produces exactly the nine canonical classes", () => {
    const decoded = decodeLoraPayload(b64("D01", EPOCH, { car: 5 }));
    expect(Object.keys(decoded.counts).sort()).toEqual(
      [...ROAD_USER_CLASSES].sort()
    );
    expect(decoded.counts.person).toBe(0);
  });

  it("carries busy-class counts above the uint8 ceiling (widened fields)", () => {
    const decoded = decodeLoraPayload(b64("D01", EPOCH, { person: 65535 }));
    expect(decoded.counts.person).toBe(65535);
  });

  it("base64 of a 20-byte frame is 28 chars, under the LoRa cap", () => {
    const payload = b64("D01", EPOCH, { person: 400 });
    expect(payload.length).toBe(28);
    expect(payload.length).toBeLessThanOrEqual(200);
  });

  it("rejects a frame of the wrong length", () => {
    const short = Buffer.alloc(19).toString("base64");
    expect(() => decodeLoraPayload(short)).toThrow(LoraDecodeError);
  });

  it("rejects an unsupported schema version", () => {
    const v1 = b64("D01", EPOCH, {}, 1);
    expect(() => decodeLoraPayload(v1)).toThrow(/schema version/);
  });

  it("rejects a non-ASCII camera id", () => {
    const buf = buildFrame("D01", EPOCH, {});
    buf.writeUInt8(0xff, 0); // corrupt first camera-id byte
    expect(() => decodeLoraPayload(buf.toString("base64"))).toThrow(
      LoraDecodeError
    );
  });
});
