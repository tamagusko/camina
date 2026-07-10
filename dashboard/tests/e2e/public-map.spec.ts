import { expect, test } from "@playwright/test";

// Smoke test for the hero view. Expects CAMINA_DATA_SOURCE=mock so the map
// renders without a backend.

test("public map renders streets", async ({ page }) => {
  await page.goto("/dublin");
  await expect(page.locator("text=Mock data")).toBeVisible();
  await expect(page.locator(".maplibregl-map")).toBeVisible();
});

test("street detail page renders for a seeded street", async ({ page, request }) => {
  // Derive a real street from the API so fixture renames can't silently
  // break this test (the old hardcoded dame-st vanished with new fixtures).
  const r = await request.get("/api/streets?city=dublin");
  expect(r.status()).toBe(200);
  const streets = (await r.json()) as Array<{ id: string; name: string }>;
  expect(streets.length).toBeGreaterThan(0);
  const street = streets[0]!;
  await page.goto(`/dublin/street/${street.id}`);
  await expect(page.getByRole("heading", { name: street.name })).toBeVisible();
});

test("privacy: no sensor fields leak into /api/streets", async ({ request }) => {
  const r = await request.get("/api/streets?city=dublin");
  expect(r.status()).toBe(200);
  const body = await r.text();
  expect(body).not.toMatch(/"sensor_id"/);
  expect(body).not.toMatch(/"latitude"/);
  expect(body).not.toMatch(/"longitude"/);
});
