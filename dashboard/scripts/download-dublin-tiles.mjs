// Pre-downloads Carto Positron raster tiles for central Dublin into
// dashboard/public/tiles/{z}/{x}/{y}.png so the map loads instantly in dev
// and is self-contained (no external CDN calls from the browser).
//
// Run with: pnpm exec node scripts/download-dublin-tiles.mjs
//
// Tile count estimate for the bbox below at zooms 12–18: ~500 tiles, ~10 MB.

import { promises as fs } from "node:fs";
import path from "node:path";

// Central Dublin bbox — generous enough to cover all sensors + surroundings.
const BBOX = {
  west: -6.31,
  south: 53.32,
  east: -6.20,
  north: 53.38,
};
const MIN_ZOOM = 12;
const MAX_ZOOM = 18;

const OUT_DIR = path.resolve(process.cwd(), "public", "tiles");
const SUBDOMAINS = ["a", "b", "c", "d"];
const PATTERN = "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png";

function lonToX(lon, z) {
  return Math.floor(((lon + 180) / 360) * Math.pow(2, z));
}
function latToY(lat, z) {
  const rad = (lat * Math.PI) / 180;
  return Math.floor(
    ((1 - Math.log(Math.tan(rad) + 1 / Math.cos(rad)) / Math.PI) / 2) * Math.pow(2, z)
  );
}

async function downloadTile(z, x, y, subIdx, concurrentCount) {
  const dir = path.join(OUT_DIR, String(z), String(x));
  const file = path.join(dir, `${y}.png`);
  try {
    await fs.access(file);
    return { status: "skip", file };
  } catch {
    // continue to download
  }
  await fs.mkdir(dir, { recursive: true });
  const url = PATTERN
    .replace("{s}", SUBDOMAINS[subIdx % SUBDOMAINS.length])
    .replace("{z}", String(z))
    .replace("{x}", String(x))
    .replace("{y}", String(y));
  const r = await fetch(url, {
    headers: {
      "User-Agent": "CAMINA-tile-downloader/0.1 (research dev; tamagusko@gmail.com)",
    },
  });
  if (!r.ok) return { status: "fail", file, code: r.status };
  const buf = Buffer.from(await r.arrayBuffer());
  await fs.writeFile(file, buf);
  return { status: "ok", file, size: buf.length };
}

async function main() {
  await fs.mkdir(OUT_DIR, { recursive: true });
  let total = 0;
  let ok = 0;
  let skip = 0;
  let fail = 0;
  let bytes = 0;

  const tasks = [];
  for (let z = MIN_ZOOM; z <= MAX_ZOOM; z++) {
    const x0 = lonToX(BBOX.west, z);
    const x1 = lonToX(BBOX.east, z);
    const y0 = latToY(BBOX.north, z);
    const y1 = latToY(BBOX.south, z);
    for (let x = Math.min(x0, x1); x <= Math.max(x0, x1); x++) {
      for (let y = Math.min(y0, y1); y <= Math.max(y0, y1); y++) {
        tasks.push({ z, x, y });
      }
    }
  }
  console.log(`Queued ${tasks.length} tiles across zooms ${MIN_ZOOM}–${MAX_ZOOM}.`);

  // Limit to ~8 concurrent requests so we don't overwhelm Carto or our network.
  const CONCURRENCY = 8;
  let idx = 0;
  async function worker(id) {
    while (idx < tasks.length) {
      const myIdx = idx++;
      const t = tasks[myIdx];
      total++;
      const r = await downloadTile(t.z, t.x, t.y, id, CONCURRENCY);
      if (r.status === "ok") {
        ok++;
        bytes += r.size ?? 0;
      } else if (r.status === "skip") {
        skip++;
      } else {
        fail++;
        console.warn(`  fail z=${t.z} x=${t.x} y=${t.y} (${r.code})`);
      }
      if (total % 50 === 0) {
        console.log(`  progress: ${total}/${tasks.length} (ok=${ok} skip=${skip} fail=${fail})`);
      }
    }
  }
  await Promise.all(
    Array.from({ length: CONCURRENCY }, (_, i) => worker(i))
  );

  console.log(
    `\nDone: ${ok} downloaded, ${skip} already cached, ${fail} failed. ` +
    `${(bytes / 1024 / 1024).toFixed(1)} MB written.`
  );
  console.log(`Tiles at ${OUT_DIR}/`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
