// MapLibre GL 6 derives its worker URL from `import.meta.url`, which no longer
// points next to the worker file once Next bundles the library: the browser
// fetches the page's HTML as the worker and the map never starts. So serve the
// worker and the chunk it imports as static files, copied from the installed
// package on every dev/build (never stale), and point `setWorkerUrl` at them
// (src/components/map/StreetMap.tsx).
import { copyFileSync, mkdirSync } from "node:fs";
import path from "node:path";

const dist = path.join(process.cwd(), "node_modules", "maplibre-gl", "dist");
const out = path.join(process.cwd(), "public", "maplibre");
mkdirSync(out, { recursive: true });
for (const file of ["maplibre-gl-worker.mjs", "maplibre-gl-shared.mjs"]) {
  copyFileSync(path.join(dist, file), path.join(out, file));
}
