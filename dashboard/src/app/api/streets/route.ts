import { NextResponse } from "next/server";
import { streetsRepo } from "@/lib/repo";

// Public list of active streets. Never exposes sensor or GPS data.
export async function GET(request: Request) {
  const url = new URL(request.url);
  const city = url.searchParams.get("city") ?? "dublin";
  const streets = await streetsRepo.list(city);
  return NextResponse.json(streets, {
    headers: {
      "Cache-Control": "public, s-maxage=60, stale-while-revalidate=300",
    },
  });
}
