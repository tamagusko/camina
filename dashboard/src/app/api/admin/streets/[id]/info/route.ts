import { NextResponse } from "next/server";
import { requireAdmin } from "@/lib/auth";
import { isMock } from "@/lib/data-source";
import { streetsRepo } from "@/lib/repo";

interface Ctx {
  params: Promise<{ id: string }>;
}

// Returns sensor identifiers and GPS for a given street.
// Gated: admin-only. In mock/dev mode we allow anyone since there's no real
// personal data, so the dev can preview the admin panel without Google OAuth.
export async function GET(_req: Request, { params }: Ctx) {
  const { id } = await params;

  if (!isMock) {
    const { session, isAdmin } = await requireAdmin();
    if (!session) return NextResponse.json({ error: "unauth" }, { status: 401 });
    if (!isAdmin) return NextResponse.json({ error: "forbidden" }, { status: 403 });
  }

  const info = await streetsRepo.adminInfo(id);
  if (!info) return NextResponse.json({ error: "not_found" }, { status: 404 });
  return NextResponse.json(info);
}
