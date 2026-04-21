import { NextResponse } from "next/server";
import { dataSource } from "@/lib/data-source";

export async function GET() {
  return NextResponse.json({
    ok: true,
    data_source: dataSource,
    ts: new Date().toISOString(),
  });
}
