// Adversary for the k-anonymity tests: given one public response, try to
// recover a suppressed value (1..K_MIN-1) by subtraction from the values shown
// alongside it. Shared by the privacy tests; not a test file itself.

import {
  ROAD_USER_CLASSES,
  type MetricValue,
  type RoadUserClass,
  type StreetReading,
  type TimeWindow,
} from "@/lib/types";
import type { StreetsRepo } from "@/lib/repo/types";

const K_MIN = 5;
// Upper bound for a hidden direction cell (it may be hidden by complementary
// suppression, so it is not limited to 1..4).
const H = 200;

function range(lo: number, hi: number): number[] {
  return Array.from({ length: hi - lo + 1 }, (_, i) => lo + i);
}

/**
 * For one class in one bucket the adversary knows the count c and, when the
 * bucket carries direction data, AB = a and BA = b with a + b = c. A hidden
 * count is in 1..4 (only the k-floor hides a count); a hidden direction cell is
 * any positive integer. Returns a description of every hidden cell that has
 * exactly one feasible value.
 */
function tripleLeaks(c: number | null, a: number | null, b: number | null): string[] {
  const cDom = c === null ? range(1, K_MIN - 1) : [c];
  const aDom = a === null ? range(1, H) : [a];
  const bDom = b === null ? range(1, H) : [b];
  const feasible = { c: new Set<number>(), a: new Set<number>(), b: new Set<number>() };
  for (const cv of cDom) {
    for (const av of aDom) {
      const bv = cv - av;
      if (!bDom.includes(bv)) continue;
      feasible.c.add(cv);
      feasible.a.add(av);
      feasible.b.add(bv);
    }
  }
  const leaks: string[] = [];
  if (c === null && feasible.c.size === 1) leaks.push(`count=${[...feasible.c][0]}`);
  if (a === null && feasible.a.size === 1) leaks.push(`AB=${[...feasible.a][0]}`);
  if (b === null && feasible.b.size === 1) leaks.push(`BA=${[...feasible.b][0]}`);
  return leaks;
}

/** Every suppressed cell recoverable from a readings response. */
export function readingLeaks(rows: StreetReading[]): string[] {
  const leaks: string[] = [];
  for (const row of rows) {
    if (row.missing || !row.countsByDirection) continue;
    for (const cls of ROAD_USER_CLASSES) {
      for (const leak of tripleLeaks(
        row.counts[cls],
        row.countsByDirection.AB[cls],
        row.countsByDirection.BA[cls]
      )) {
        leaks.push(`${row.bucket} ${cls} ${leak}`);
      }
    }
  }
  return leaks;
}

/**
 * Street totals must add no information beyond the per-class values shown: a
 * total equal to the sum of the published cells leaves every hidden class
 * unconstrained. Returns every row where the total is not that sum.
 */
export function metricLeaks(rows: MetricValue[], metric: "counts" | "speed"): string[] {
  const leaks: string[] = [];
  for (const row of rows) {
    const shown = Object.values(row.classBreakdown);
    const sum = shown.reduce<number>((acc, v) => acc + (v ?? 0), 0);
    const hidden = shown.some((v) => v === null);
    const expected = sum;
    if (row.totalCount !== expected) {
      leaks.push(`${row.streetId} totalCount=${row.totalCount} published sum=${sum}`);
    }
    // A null class count is a hidden cell, so the flag must be set. The flag
    // may also be set with no null shown: a window sums published 15-min
    // cells and leaves hidden ones out.
    if (hidden && !row.hasHidden) leaks.push(`${row.streetId} hasHidden=${row.hasHidden}`);
    if (metric === "counts" && row.value !== expected) {
      leaks.push(`${row.streetId} value=${row.value} published sum=${sum}`);
    }
    for (const v of shown) {
      if (v !== null && v >= 1 && v < K_MIN) leaks.push(`${row.streetId} class count ${v}`);
    }
  }
  return leaks;
}

// ---------------------------------------------------------------------------
// Across aggregation levels. The atomic published cell is (street, class,
// 15-min window). Every coarser number (60/1440-min buckets, metrics windows,
// totals under a class filter) is an observation over a set of classes and a
// time interval. Differencing two nested observations, or one observation
// against the 15-min cells under it, gives the sum of the cells in between; if
// that residual is not the sum of the published cells there, it says
// something about the hidden ones.

const CELL_MS = 15 * 60_000;

export interface Observation {
  label: string;
  classes: readonly RoadUserClass[];
  from: number; // ms, inclusive
  to: number; // ms, exclusive
  value: number | null;
  hasHidden?: boolean;
}

export interface AggregationReport {
  /** Differences that carry information about hidden cells (residual != 0). */
  leaks: string[];
  /** Hidden 15-min cells the adversary pins to one value (each cell once). */
  recovered: string[];
  /** Nested pairs of observations differenced (including against the grid). */
  pairs: number;
  /** Hidden 15-min cells lying under some published coarser observation. */
  targets: number;
}

/**
 * `grid` is the published 15-min readings of one street, all classes. A missing
 * window has no data (a true 0). A hidden cell (null) is 1..4.
 */
export function aggregationLeaks(
  street: string,
  grid: StreetReading[],
  observations: Observation[]
): AggregationReport {
  const times = grid.map((row) => new Date(row.bucket).getTime());
  const start = times[0] ?? 0;
  const n = grid.length;
  // Prefix sums per class of published values and of hidden-cell counts.
  const pub = new Map<RoadUserClass, number[]>();
  const hid = new Map<RoadUserClass, number[]>();
  for (const cls of ROAD_USER_CLASSES) {
    const p = [0];
    const h = [0];
    for (const row of grid) {
      const v = row.missing ? 0 : row.counts[cls];
      p.push(p.at(-1)! + (v ?? 0));
      h.push(h.at(-1)! + (v === null ? 1 : 0));
    }
    pub.set(cls, p);
    hid.set(cls, h);
  }
  const index = (t: number) => Math.min(n, Math.max(0, Math.ceil((t - start) / CELL_MS)));
  const over = (o: Observation) => {
    const i = index(o.from);
    const j = index(o.to);
    let sum = 0;
    let hidden = 0;
    for (const cls of o.classes) {
      sum += pub.get(cls)![j]! - pub.get(cls)![i]!;
      hidden += hid.get(cls)![j]! - hid.get(cls)![i]!;
    }
    return { sum, hidden };
  };
  const hiddenCells = (o: Observation, inner?: Observation) => {
    const cells: string[] = [];
    for (const cls of o.classes) {
      for (let k = index(o.from); k < index(o.to); k++) {
        if (grid[k]!.missing || grid[k]!.counts[cls] !== null) continue;
        const t = times[k]!;
        const insideInner =
          inner && inner.classes.includes(cls) && t >= inner.from && t < inner.to;
        if (!insideInner) cells.push(`${street} ${cls} ${grid[k]!.bucket}`);
      }
    }
    return cells;
  };

  const report: AggregationReport = { leaks: [], recovered: [], pairs: 0, targets: 0 };
  const targets = new Set<string>();
  const recovered = new Map<string, string>();
  const judge = (outer: Observation, inner: Observation | null) => {
    const a = over(outer);
    const b = inner ? over(inner) : { sum: 0, hidden: 0 };
    const residual = outer.value! - (inner ? inner.value! : 0) - (a.sum - b.sum);
    const s = a.hidden - b.hidden;
    report.pairs += 1;
    const what = inner ? `${outer.label} − ${inner.label}` : `${outer.label} − 15-min cells`;
    if (residual === 0) return;
    report.leaks.push(`${what}: residual ${residual} over ${s} hidden cells`);
    // Each hidden cell is 1..4; the residual pins them all when S = 1, or when
    // it sits at either end of [S, 4S].
    const exact = (s === 1 && residual >= 1 && residual <= K_MIN - 1) ||
      (s > 0 && (residual === s || residual === (K_MIN - 1) * s));
    if (!exact) return;
    const each = s === 1 ? residual : residual / s;
    for (const cell of hiddenCells(outer, inner ?? undefined)) {
      if (!recovered.has(cell)) recovered.set(cell, `${cell} = ${each} (${what})`);
    }
  };

  const published = observations.filter((o) => o.value !== null);
  for (const o of published) {
    const { hidden } = over(o);
    if (hidden > 0) for (const cell of hiddenCells(o)) targets.add(cell);
    if (o.hasHidden !== undefined && o.hasHidden !== hidden > 0) {
      report.leaks.push(`${o.label}: hasHidden=${o.hasHidden} but ${hidden} hidden cells under it`);
    }
    judge(o, null);
  }
  const contains = (a: Observation, b: Observation) =>
    a !== b && a.from <= b.from && b.to <= a.to &&
    b.classes.every((cls) => a.classes.includes(cls)) &&
    (a.from !== b.from || a.to !== b.to || a.classes.length !== b.classes.length);
  for (const a of published) for (const b of published) if (contains(a, b)) judge(a, b);
  report.targets = targets.size;
  report.recovered = [...recovered.values()];
  return report;
}

const WINDOW_MS: Record<TimeWindow, number> = {
  now: 15 * 60_000,
  "1h": 60 * 60_000,
  "24h": 24 * 60 * 60_000,
  "7d": 7 * 24 * 60 * 60_000,
  "30d": 30 * 24 * 60 * 60_000,
};

/**
 * Ask the repo for every aggregation level over [from, to) — readings at 15,
 * 60 and 1440 min (all classes and under a class filter), and latestMetrics
 * for every window, all classes and each leave-one-out class filter — and run
 * the adversary street by street against the 15-min grid of the last 30 d.
 * `now` is the instant latestMetrics measures its windows back from.
 */
export async function attackAggregation(
  repo: StreetsRepo,
  city: string,
  from: Date,
  to: Date,
  now: Date
): Promise<AggregationReport> {
  const streets = (await repo.list(city)).map((s) => s.id);
  const all = [...ROAD_USER_CLASSES];
  const filters: RoadUserClass[][] = [all, ...all.map((x) => all.filter((c) => c !== x))];
  const metrics = new Map<string, Observation[]>(streets.map((id) => [id, []]));
  for (const window of Object.keys(WINDOW_MS) as TimeWindow[]) {
    const wFrom = now.getTime() - WINDOW_MS[window];
    for (const classes of filters) {
      const rows = await repo.latestMetrics({
        city, metric: "counts", window,
        classes: classes.length === all.length ? undefined : classes,
      });
      const tag = classes.length === all.length ? "all" : `all−${all.find((c) => !classes.includes(c))}`;
      for (const row of rows) {
        const obs = metrics.get(row.streetId);
        if (!obs) continue;
        obs.push({
          label: `metrics ${window} ${tag} total`, classes, from: wFrom, to: now.getTime(),
          value: row.totalCount, hasHidden: row.hasHidden,
        });
        if (classes.length !== all.length) continue;
        for (const cls of all) {
          obs.push({
            label: `metrics ${window} ${cls}`, classes: [cls], from: wFrom, to: now.getTime(),
            value: row.classBreakdown[cls],
          });
        }
      }
    }
  }
  const report: AggregationReport = { leaks: [], recovered: [], pairs: 0, targets: 0 };
  for (const street of streets) {
    // The 15-min grid spans every metrics window, back to 30 d.
    const grid = await repo.readings({
      streetId: street, from: new Date(now.getTime() - WINDOW_MS["30d"]), to, bucketMinutes: 15,
    });
    const obs = [...metrics.get(street)!];
    for (const bucketMinutes of [60, 1440]) {
      for (const classes of [undefined, ["e-scooter", "cyclist"] as RoadUserClass[]]) {
        const rows = await repo.readings({ streetId: street, classes, from, to, bucketMinutes });
        for (const row of rows) {
          if (row.missing) continue;
          const t = new Date(row.bucket).getTime();
          for (const cls of classes ?? all) {
            obs.push({
              label: `${bucketMinutes}-min ${row.bucket} ${cls}${classes ? " (filtered)" : ""}`,
              classes: [cls], from: Math.max(t, from.getTime()),
              to: Math.min(t + bucketMinutes * 60_000, to.getTime()), value: row.counts[cls],
            });
          }
        }
      }
    }
    const r = aggregationLeaks(street, grid, obs);
    report.leaks.push(...r.leaks);
    report.recovered.push(...r.recovered);
    report.pairs += r.pairs;
    report.targets += r.targets;
  }
  return report;
}
