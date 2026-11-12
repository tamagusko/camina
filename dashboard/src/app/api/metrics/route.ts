import { NextResponse } from "next/server";
import { streetsRepo } from "@/lib/repo";
import { metricsQuerySchema } from "@/lib/schemas";

// Current metric values per street for the city map paint.
// Separate from /api/streets so the basemap geometry stays cacheable while
// the metric payload refreshes on filter change.
export async function GET(request: Request) {
  const url = new URL(request.url);
  const classes = url.searchParams.getAll("class");
  const parsed = metricsQuerySchema.safeParse({
    city: url.searchParams.get("city") ?? undefined,
    metric: url.searchParams.get("metric") ?? undefined,
    window: url.searchParams.get("window") ?? undefined,
    class: classes.length ? classes : undefined,
  });
  if (!parsed.success) {
    return NextResponse.json({ error: "bad_query", issues: parsed.error.issues }, { status: 400 });
  }
  const q = parsed.data;
  const metrics = await streetsRepo.latestMetrics({
    city: q.city,
    metric: q.metric,
    classes: q.class,
    window: q.window,
  });
  return NextResponse.json(metrics, {
    headers: { "Cache-Control": "public, s-maxage=30, stale-while-revalidate=120" },
  });
}
