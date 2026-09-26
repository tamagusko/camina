// Adversary for the k-anonymity tests: given one public response, try to
// recover a suppressed value (1..K_MIN-1) by subtraction from the values shown
// alongside it. Shared by the privacy tests; not a test file itself.

import { ROAD_USER_CLASSES, type MetricValue, type StreetReading } from "@/lib/types";

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
    if (row.hasHidden !== hidden) leaks.push(`${row.streetId} hasHidden=${row.hasHidden}`);
    if (metric === "counts" && row.value !== expected) {
      leaks.push(`${row.streetId} value=${row.value} published sum=${sum}`);
    }
    for (const v of shown) {
      if (v !== null && v >= 1 && v < K_MIN) leaks.push(`${row.streetId} class count ${v}`);
    }
  }
  return leaks;
}
