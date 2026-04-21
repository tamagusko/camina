// Opens a headed Chromium at the dashboard and stays open.
// Kill with Ctrl+C or close the window.

import { chromium } from "@playwright/test";

const URL = process.env.URL ?? "http://localhost:3000/dublin";
const VIEWPORT = { width: 1440, height: 900 };

const browser = await chromium.launch({
  headless: false,
  args: [`--window-size=${VIEWPORT.width},${VIEWPORT.height}`],
});
const context = await browser.newContext({ viewport: VIEWPORT });
const page = await context.newPage();

page.on("console", (msg) => console.log(`[${msg.type()}] ${msg.text()}`));
page.on("pageerror", (err) => console.error(`[pageerror] ${err.message}`));

await page.goto(URL);
console.log(`\n✓ Opened ${URL} in a ${VIEWPORT.width}×${VIEWPORT.height} window.`);
console.log("  Interact with it, then press Ctrl+C here to close.\n");

// Keep the process alive until the window is closed or Ctrl+C is hit.
await new Promise((resolve) => {
  page.on("close", resolve);
  browser.on("disconnected", resolve);
});
await browser.close();
