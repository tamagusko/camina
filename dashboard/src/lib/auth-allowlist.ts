import "server-only";
import { sql, type SQL } from "drizzle-orm";

export type AllowedRole = "admin" | "viewer";

export interface AccountAccess {
  email: string;
  role: AllowedRole;
}

export interface AllowlistDatabase {
  execute(query: SQL): Promise<unknown>;
}

function firstRow(result: unknown): Record<string, unknown> | undefined {
  if (Array.isArray(result)) return result[0] as Record<string, unknown> | undefined;
  const rows = (result as { rows?: unknown[] })?.rows;
  return Array.isArray(rows)
    ? (rows[0] as Record<string, unknown> | undefined)
    : undefined;
}

function allowedRole(value: unknown): AllowedRole | null {
  return value === "admin" || value === "viewer" ? value : null;
}

/** Resolve an account against the live database, with exact members taking precedence. */
export async function resolveLiveAccess(
  rawEmail: string,
  database: AllowlistDatabase
): Promise<AccountAccess | null> {
  const email = rawEmail.trim().toLowerCase();
  const separator = email.lastIndexOf("@");
  if (separator <= 0 || separator === email.length - 1) return null;
  const domain = email.slice(separator + 1);

  const result = await database.execute(sql`
    SELECT
      (SELECT role FROM allowed_members WHERE lower(email) = ${email} LIMIT 1) AS member_role,
      (SELECT default_role FROM allowed_domains WHERE lower(domain) = ${domain} LIMIT 1) AS domain_role
  `);
  const row = firstRow(result);
  const role = allowedRole(row?.member_role) ?? allowedRole(row?.domain_role);
  return role ? { email, role } : null;
}
