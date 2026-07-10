import "server-only";
import { ROAD_USER_CLASSES, type RoadUserClass } from "./types";

// TypeScript decoder for the Phase-4 LoRaWAN binary frame. The mirror of
// `src/camina/io/lora_codec.py` (`pack`). TTN forwards the raw uplink bytes
// base64-encoded as `uplink_message.frm_payload`; this module decodes them back
// into the nine-class counts. See `docs/lora.md` for the byte layout and the
// duty-cycle / airtime budget.
//
// Wire format (schema version 2, big-endian, 20 bytes):
//   off size field          type
//   0   3    camera id      ascii  ("LNN"/"DNN", e.g. "D01")
//   3   4    window start   uint32 (unix epoch seconds, UTC)
//   7   2    person         uint16  ── busy classes widened to 2 bytes because
//   9   2    cyclist        uint16     the simulation showed person peaks of
//   11  2    car            uint16     259–425/window overflow a uint8
//   13  1    e-scooter      uint8
//   14  1    SUV            uint8
//   15  1    motorcyclist   uint8
//   16  1    bus            uint8
//   17  1    delivery_van   uint8
//   18  1    truck          uint8
//   19  1    schema version uint8  (== 2)
//
// Class order is load-bearing and MUST match `ROAD_USER_CLASSES` (types.ts),
// `CLASSES` in scripts/generate_mock_dublin.py, and `CLASSES` in lora_codec.py.

export const LORA_SCHEMA_VERSION = 2;
export const LORA_FRAME_BYTES = 20;

// Classes carried as uint16 (offsets 7,9,11). The remaining six are uint8.
const WIDE_CLASSES: ReadonlySet<RoadUserClass> = new Set([
  "person",
  "cyclist",
  "car",
]);

export interface LoraDecoded {
  cameraId: string;
  windowStart: string; // ISO-8601 UTC
  counts: Record<RoadUserClass, number>;
  schemaVersion: number;
}

export class LoraDecodeError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "LoraDecodeError";
  }
}

/** Decode a base64 TTN `frm_payload` into the nine-class window record. */
export function decodeLoraPayload(frmPayloadB64: string): LoraDecoded {
  // Buffer.from silently drops invalid base64 chars, so we guard on the
  // decoded byte length rather than trusting the input string.
  const bytes = Buffer.from(frmPayloadB64, "base64");
  if (bytes.length !== LORA_FRAME_BYTES) {
    throw new LoraDecodeError(
      `LoRa frame must be ${LORA_FRAME_BYTES} bytes, got ${bytes.length}`
    );
  }

  const schemaVersion = bytes.readUInt8(19);
  if (schemaVersion !== LORA_SCHEMA_VERSION) {
    throw new LoraDecodeError(
      `unsupported LoRa schema version ${schemaVersion} (expected ${LORA_SCHEMA_VERSION})`
    );
  }

  const cameraId = bytes.toString("ascii", 0, 3);
  // ascii decode maps bytes ≥128 to mojibake; enforce printable 7-bit ASCII.
  if (!/^[\x20-\x7e]{3}$/.test(cameraId)) {
    throw new LoraDecodeError("camera id is not 3 printable ASCII bytes");
  }

  const epochSeconds = bytes.readUInt32BE(3);
  const windowStart = new Date(epochSeconds * 1000).toISOString();

  const counts = {} as Record<RoadUserClass, number>;
  let offset = 7;
  for (const cls of ROAD_USER_CLASSES) {
    if (WIDE_CLASSES.has(cls)) {
      counts[cls] = bytes.readUInt16BE(offset);
      offset += 2;
    } else {
      counts[cls] = bytes.readUInt8(offset);
      offset += 1;
    }
  }

  return { cameraId, windowStart, counts, schemaVersion };
}
