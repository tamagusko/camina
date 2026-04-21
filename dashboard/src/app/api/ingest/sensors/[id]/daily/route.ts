import { NextResponse } from "next/server";
import { dailyPayloadSchema } from "@/lib/schemas";
import { verifyIngestToken } from "@/lib/ingest-auth";
import { isMock } from "@/lib/data-source";

interface Ctx {
  params: Promise<{ id: string }>;
}

export async function POST(request: Request, { params }: Ctx) {
  const { id } = await params;
  const authError = verifyIngestToken(request, id);
  if (authError) return authError;

  const body = await request.json().catch(() => null);
  const parsed = dailyPayloadSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json({ error: "bad_payload", issues: parsed.error.issues }, { status: 400 });
  }
  if (parsed.data.sensor_id !== id) {
    return NextResponse.json({ error: "sensor_id_mismatch" }, { status: 400 });
  }
  if (isMock) {
    return NextResponse.json({ ok: true, latest_config_version: parsed.data.config_version });
  }
  return NextResponse.json({ error: "live_mode_not_implemented" }, { status: 501 });
}
