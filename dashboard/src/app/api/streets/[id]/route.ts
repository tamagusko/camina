import { NextResponse } from "next/server";
import { streetsRepo } from "@/lib/repo";

interface Ctx {
  params: Promise<{ id: string }>;
}

export async function GET(_req: Request, { params }: Ctx) {
  const { id } = await params;
  const street = await streetsRepo.get(id);
  if (!street) return NextResponse.json({ error: "not_found" }, { status: 404 });
  return NextResponse.json(street, {
    headers: { "Cache-Control": "public, s-maxage=60, stale-while-revalidate=300" },
  });
}
