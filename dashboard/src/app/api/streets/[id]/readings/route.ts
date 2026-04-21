import { NextResponse } from "next/server";
import { streetsRepo } from "@/lib/repo";
import { readingsQuerySchema } from "@/lib/schemas";

interface Ctx {
  params: Promise<{ id: string }>;
}

export async function GET(request: Request, { params }: Ctx) {
  const { id } = await params;
  const url = new URL(request.url);
  const parsed = readingsQuerySchema.safeParse({
    metric: url.searchParams.get("metric") ?? undefined,
    class: url.searchParams.getAll("class").length
      ? url.searchParams.getAll("class")
      : undefined,
    from: url.searchParams.get("from") ?? undefined,
    to: url.searchParams.get("to") ?? undefined,
    bucket: url.searchParams.get("bucket") ?? undefined,
  });
  if (!parsed.success) {
    return NextResponse.json({ error: "bad_query", issues: parsed.error.issues }, { status: 400 });
  }
  const q = parsed.data;
  const to = q.to ? new Date(q.to) : new Date();
  const from = q.from ? new Date(q.from) : new Date(to.getTime() - 60 * 60_000);
  const readings = await streetsRepo.readings({
    streetId: id,
    classes: q.class,
    from,
    to,
    bucketMinutes: q.bucket,
  });
  return NextResponse.json(readings, {
    headers: { "Cache-Control": "public, s-maxage=60, stale-while-revalidate=300" },
  });
}
