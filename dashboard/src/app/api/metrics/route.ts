import { NextResponse } from "next/server";
import { streetsRepo } from "@/lib/repo";
import {
  classSchema,
  metricSchema,
  timeWindowSchema,
} from "@/lib/schemas";
import type { RoadUserClass } from "@/lib/types";

// Current metric values per street for the city map paint.
// Separate from /api/streets so the basemap geometry stays cacheable while
// the metric payload refreshes on filter change.
export async function GET(request: Request) {
  const url = new URL(request.url);
  const city = url.searchParams.get("city") ?? "dublin";
  const metric = metricSchema.parse(url.searchParams.get("metric") ?? "counts");
  const window = timeWindowSchema.parse(url.searchParams.get("window") ?? "1h");
  const classes = url.searchParams.getAll("class");
  const parsedClasses: RoadUserClass[] | undefined = classes.length
    ? classes.map((c) => classSchema.parse(c))
    : undefined;

  const metrics = await streetsRepo.latestMetrics({
    city,
    metric,
    classes: parsedClasses,
    window,
  });
  return NextResponse.json(metrics, {
    headers: { "Cache-Control": "public, s-maxage=30, stale-while-revalidate=120" },
  });
}
