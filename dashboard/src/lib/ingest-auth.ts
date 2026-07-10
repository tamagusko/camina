import "server-only";
import { createHash } from "node:crypto";
import { NextResponse } from "next/server";
import { isMock } from "@/lib/data-source";
import {
  findSensorIdByTokenHash,
  getSensorTokenHash,
} from "@/lib/ingest-store";
import { secureCompare } from "@/lib/secure-compare";

// Per-device Bearer-token check for ingest routes (H6).
//
// Audit decision: SHA-256, NOT bcrypt. The token is already high-entropy
// (a random per-device secret), so a fast hash is preimage-safe here; bcrypt
// would waste 50-250 ms of CPU per request for no security gain.
//
// A shared CAMINA_DEV_INGEST_TOKEN stays for mock/dev so the Python sensor
// daemon can post without a provisioned DB.

const DEV_TOKEN = process.env.CAMINA_DEV_INGEST_TOKEN;

export interface IngestAuthDeps {
  getSensorTokenHash: (sensorId: string) => Promise<string | null>;
  findSensorIdByTokenHash: (tokenHash: string) => Promise<string | null>;
}

const defaultDeps: IngestAuthDeps = {
  getSensorTokenHash,
  findSensorIdByTokenHash,
};

function sha256Hex(value: string): string {
  return createHash("sha256").update(value).digest("hex");
}

export async function verifyIngestToken(
  request: Request,
  sensorId: string,
  deps: IngestAuthDeps = defaultDeps
): Promise<NextResponse | null> {
  const header = request.headers.get("authorization") ?? "";
  const token = header.match(/^Bearer\s+(.+)$/i)?.[1];

  if (!token) {
    return NextResponse.json({ error: "missing_token" }, { status: 401 });
  }

  // Shared dev token (mock/dev only).
  if (DEV_TOKEN && secureCompare(token, DEV_TOKEN)) return null;

  // Mock mode provisions no per-sensor tokens; only the dev token is valid.
  if (isMock) {
    return NextResponse.json(
      { error: "invalid_token", sensor_id: sensorId },
      { status: 401 }
    );
  }

  // Live: compare the SHA-256 of the presented token against the stored
  // per-sensor hash using the constant-time helper.
  const presentedHash = sha256Hex(token);
  const storedHash = await deps.getSensorTokenHash(sensorId);
  if (storedHash && secureCompare(presentedHash, storedHash)) return null;

  // Not this sensor's token — if it belongs to a different sensor, the caller
  // is using the wrong sensor id in the path (403); otherwise it is invalid.
  const owner = await deps.findSensorIdByTokenHash(presentedHash);
  if (owner && owner !== sensorId) {
    return NextResponse.json(
      { error: "sensor_token_mismatch", sensor_id: sensorId },
      { status: 403 }
    );
  }
  return NextResponse.json(
    { error: "invalid_token", sensor_id: sensorId },
    { status: 401 }
  );
}
