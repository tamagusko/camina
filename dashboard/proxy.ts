// Next.js 16+ network-boundary proxy (renamed from middleware.ts).
//
// Per the platform guidance, proxy.ts is NOT the auth layer — auth lives in
// layouts and server components. This file carries only light-weight
// request-rewrites and security headers that need to run at the edge of the
// request lifecycle.

import { NextResponse } from "next/server";

export function proxy(request: Request) {
  const response = NextResponse.next();
  // Defence-in-depth security headers on every response.
  response.headers.set("X-Content-Type-Options", "nosniff");
  response.headers.set("Referrer-Policy", "strict-origin-when-cross-origin");
  response.headers.set("Permissions-Policy", "camera=(), microphone=(), geolocation=()");
  return response;
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
