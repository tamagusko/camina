// Diagnostic: launch chromium, visit the dashboard, dump console + DOM sizes.
// Run with: pnpm exec node scripts/inspect-map.mjs

import { chromium } from "@playwright/test";

const URL = process.env.URL ?? "http://localhost:3000/dublin";

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await context.newPage();

const logs = [];
page.on("console", (msg) => logs.push(`[${msg.type()}] ${msg.text()}`));
page.on("pageerror", (err) => logs.push(`[error] ${err.message}`));

await page.goto(URL, { waitUntil: "networkidle" });
await page.waitForTimeout(1500);

const dom = await page.evaluate(() => {
  const canvas = document.querySelector(".maplibregl-canvas");
  if (!canvas) return { error: "no canvas found" };
  const walk = [];
  let cur = canvas;
  while (cur) {
    const r = cur.getBoundingClientRect();
    const cs = getComputedStyle(cur);
    walk.push({
      tag: cur.tagName.toLowerCase(),
      cls: (cur.getAttribute("class") ?? "").slice(0, 80),
      rect: { w: Math.round(r.width), h: Math.round(r.height) },
      position: cs.position,
      width: cs.width,
      height: cs.height,
      inset: cs.inset,
    });
    cur = cur.parentElement;
  }
  return {
    window: { w: innerWidth, h: innerHeight },
    canvasAttrs: {
      width: canvas.getAttribute("width"),
      height: canvas.getAttribute("height"),
      styleWidth: canvas.style.width,
      styleHeight: canvas.style.height,
    },
    chain: walk,
  };
});

const failed = await page.evaluate(() => {
  return performance.getEntriesByType("resource")
    .filter((e) => e.initiatorType === "img" && (e.name.includes("cartocdn") || e.name.includes("openstreet")))
    .slice(0, 5)
    .map((e) => ({ url: e.name, duration: Math.round(e.duration), transferSize: e.transferSize }));
});

await page.screenshot({ path: "scripts/camina-preview.png", fullPage: false });
await browser.close();

console.log("\n=== CONSOLE ===");
logs.forEach((l) => console.log(l));
console.log("\n=== DOM CHAIN (from .maplibregl-map up) ===");
console.log(JSON.stringify(dom, null, 2));
console.log("\n=== TILE REQUESTS ===");
console.log(JSON.stringify(failed, null, 2));
console.log("\nScreenshot written to scripts/camina-preview.png");
