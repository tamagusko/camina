import { NextResponse } from "next/server";
import { verifyIngestToken } from "@/lib/ingest-auth";
import { checkIngestRateLimit } from "@/lib/ingest-ratelimit";
import { readSensorConfig } from "@/lib/ingest-store";
import { isMock } from "@/lib/data-source";
import { sensorConfigResponseSchema } from "@/lib/schemas";
import { MOCK_CONFIG } from "@/lib/mock-sensor-config";

interface Ctx {
  params: Promise<{ id: string }>;
}

export async function GET(request: Request, { params }: Ctx) {
  const { id } = await params;

  const limited = await checkIngestRateLimit(request, id);
  if (limited) return limited;

  const authError = await verifyIngestToken(request, id);
  if (authError) return authError;

  if (isMock) return NextResponse.json(sensorConfigResponseSchema.parse(MOCK_CONFIG));
  // Live mode: return the sensor's stored config (removes the 501 stub).
  const cfg = await readSensorConfig(id);
  if (!cfg) return NextResponse.json({ error: "unknown_sensor" }, { status: 404 });
  const response = sensorConfigResponseSchema.safeParse({
    ...cfg.config,
    config_version: cfg.config_version,
  });
  if (!response.success) {
    return NextResponse.json({ error: "invalid_sensor_config" }, { status: 500 });
  }
  return NextResponse.json(response.data);
}
