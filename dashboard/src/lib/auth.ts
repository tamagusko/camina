import "server-only";
import NextAuth from "next-auth";
import Google from "next-auth/providers/google";
import { isProduction } from "@/lib/env";

// Auth.js v5 configuration. Google SSO only.
//
// Allowlist is DB-backed (tables `allowed_members` + `allowed_domains`).
// Until the live DB lands, the allowlist is stubbed via env var
// CAMINA_DEV_ALLOWED_EMAILS (comma-separated) for local dev.

const devAllowlist = (process.env.CAMINA_DEV_ALLOWED_EMAILS ?? "")
  .split(",")
  .map((s) => s.trim().toLowerCase())
  .filter(Boolean);

const devAdminList = (process.env.CAMINA_DEV_ADMIN_EMAILS ?? "")
  .split(",")
  .map((s) => s.trim().toLowerCase())
  .filter(Boolean);

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [Google],
  pages: {
    signIn: "/sign-in",
    error: "/sign-in/error",
  },
  callbacks: {
    async signIn({ user }) {
      const email = user.email?.toLowerCase();
      if (!email) return false;
      // Dev-mode allowlist check. Live mode will hit `allowed_members` table.
      if (devAllowlist.length === 0) {
        // Fail closed in production: an empty allowlist denies everyone.
        // In dev, accept any sign-in — convenient for first-run setup.
        return !isProduction();
      }
      return devAllowlist.includes(email);
    },
    async session({ session }) {
      const email = session.user?.email?.toLowerCase();
      (session as unknown as { role: "admin" | "viewer" }).role =
        email && devAdminList.includes(email) ? "admin" : "viewer";
      return session;
    },
  },
});

export async function requireAdmin() {
  const session = await auth();
  const role = (session as unknown as { role?: string } | null)?.role;
  return { session, isAdmin: role === "admin" };
}
