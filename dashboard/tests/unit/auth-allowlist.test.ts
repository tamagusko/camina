import { describe, expect, it } from "vitest";
import { resolveLiveAccess } from "@/lib/auth-allowlist";

function fakeDatabase(rows: unknown[]) {
  return { execute: async () => rows };
}

describe("resolveLiveAccess", () => {
  it("uses an exact member before the domain default", async () => {
    const database = fakeDatabase([{ member_role: "admin", domain_role: "viewer" }]);
    await expect(resolveLiveAccess("Person@UCD.IE", database)).resolves.toEqual({
      email: "person@ucd.ie",
      role: "admin",
    });
  });

  it("allows a domain member using its default role", async () => {
    const database = fakeDatabase([{ member_role: null, domain_role: "viewer" }]);
    await expect(resolveLiveAccess("person@ucd.ie", database)).resolves.toEqual({
      email: "person@ucd.ie",
      role: "viewer",
    });
  });

  it("refuses an account absent from both allowlists", async () => {
    const database = fakeDatabase([{ member_role: null, domain_role: null }]);
    await expect(resolveLiveAccess("person@example.net", database)).resolves.toBeNull();
  });

  it("refuses malformed email addresses without querying", async () => {
    let queried = false;
    const database = { execute: async () => { queried = true; return []; } };
    await expect(resolveLiveAccess("invalid", database)).resolves.toBeNull();
    expect(queried).toBe(false);
  });
});
