import { randomUUID } from "node:crypto";
import { afterAll, describe, expect, it } from "vitest";
import { drizzle } from "drizzle-orm/postgres-js";
import postgres from "postgres";
import { resolveLiveAccess } from "@/lib/auth-allowlist";

const databaseUrl = process.env.DATABASE_URL_TEST;
const describeLive = databaseUrl ? describe : describe.skip;

describeLive("live auth allowlist against Postgres", () => {
  const client = postgres(databaseUrl ?? "postgres://unused", { max: 1, prepare: false });
  const database = drizzle(client);
  const suffix = randomUUID();
  const domain = `${suffix}.example.test`;
  const memberEmail = `member@${domain}`;

  afterAll(async () => {
    await client`DELETE FROM allowed_members WHERE email = ${memberEmail}`;
    await client`DELETE FROM allowed_domains WHERE domain = ${domain}`;
    await client.end();
  });

  it("applies the domain role and exact-member override", async () => {
    await client`
      INSERT INTO allowed_domains (domain, default_role) VALUES (${domain}, 'viewer')
    `;
    await expect(resolveLiveAccess(`domain-user@${domain}`, database)).resolves.toEqual({
      email: `domain-user@${domain}`,
      role: "viewer",
    });

    await client`
      INSERT INTO allowed_members (email, role) VALUES (${memberEmail}, 'admin')
    `;
    await expect(resolveLiveAccess(memberEmail, database)).resolves.toEqual({
      email: memberEmail,
      role: "admin",
    });
  });
});
