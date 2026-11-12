import "server-only";
import NextAuth from "next-auth";
import Google from "next-auth/providers/google";
import { isProduction } from "@/lib/env";
import { isLive } from "@/lib/data-source";
import { db } from "@/lib/db";
import { resolveLiveAccess, type AllowedRole } from "@/lib/auth-allowlist";

// Auth.js v5 configuration. Google SSO only.
//
// Live allowlist is DB-backed (allowed_members + allowed_domains). Mock mode
// uses CAMINA_DEV_ALLOWED_EMAILS for local development.

const devAllowlist = (process.env.CAMINA_DEV_ALLOWED_EMAILS ?? "")
  .split(",")
  .map((s) => s.trim().toLowerCase())
  .filter(Boolean);

const devAdminList = (process.env.CAMINA_DEV_ADMIN_EMAILS ?? "")
  .split(",")
  .map((s) => s.trim().toLowerCase())
  .filter(Boolean);

async function accountAccess(email: string): Promise<{ role: AllowedRole } | null> {
  if (isLive) return resolveLiveAccess(email, db());
  if (devAllowlist.length === 0) {
    return isProduction() ? null : { role: devAdminList.includes(email) ? "admin" : "viewer" };
  }
  if (!devAllowlist.includes(email)) return null;
  return { role: devAdminList.includes(email) ? "admin" : "viewer" };
}

export const { handlers, auth, signIn } = NextAuth({
  providers: [Google],
  pages: {
    signIn: "/sign-in",
    error: "/sign-in/error",
  },
  callbacks: {
    async signIn({ user }) {
      const email = user.email?.toLowerCase();
      if (!email) return false;
      return (await accountAccess(email)) !== null;
    },
    async session({ session }) {
      const email = session.user?.email?.toLowerCase();
      const access = email ? await accountAccess(email) : null;
      (session as unknown as { role?: AllowedRole }).role = access?.role;
      return session;
    },
  },
});

export async function requireAdmin() {
  const session = await auth();
  const role = (session as unknown as { role?: string } | null)?.role;
  return { session, isAdmin: role === "admin" };
}
