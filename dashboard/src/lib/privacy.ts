// Public-read privacy rules, shared by the mock and live adapters.
//
// The unit of publication is the base cell: one street, one class, one 15-min
// window (and each direction cell of it). The rules below run on base cells
// only; every coarser number is built from what they publish.
//
// 1. k-floor: a published count is 0 or >= K_MIN. Counts of 1..K_MIN-1 are
//    re-identifiable and are published as null.
// 2. Direction pairs: AB + BA = count, so one hidden cell next to a shown cell
//    and a shown count is recoverable by subtraction. If either cell of a class
//    is hidden, both are hidden. A pair is also hidden when the class's
//    direction data does not cover every row in the window (mixed schema 1.0
//    and 1.1 rows), since count - AB - BA would then expose the undirected rest.
// 3. Aggregation: every coarser number (60- and 1440-min buckets, the metrics
//    windows 1h/24h/7d/30d, street totals, class totals under any class
//    filter, directions and speeds) is computed from published base cells only.
//    A coarser count is the sum of the published base cells under it, with
//    `hasHidden` set when any base cell under it was hidden; it is null when
//    that sum is 0 and a cell under it was hidden, and a coarser count of
//    1..K_MIN-1 would itself be hidden (a sum of values that are each 0 or
//    >= K_MIN cannot be one, but the rule holds regardless). A coarser
//    direction pair is published only when every base pair under it was. A
//    coarser mean speed averages only base cells whose speed was published.
//    So no published number, at any bucket size, window or class filter,
//    differs from a sum of published base cells, and differencing any two of
//    them (60 - 15, 24h - 1h, all classes - all but one) yields only published
//    cells, never a hidden one. The true total is never published: true total
//    minus the shown cells would be the hidden ones.
//
// Cost: hidden cells are left out of every sum, not rounded in. A class that
// is often 1..4 per 15 min (a quiet street at night, e-scooters) reads low over
// an hour, a day or a month, and the gap grows with the window. The API flags
// such numbers with `hasHidden`, and the UI says "Some values under 5 are
// hidden." wherever one is shown.
//
// docs/PROTOCOL.md section 4.1 points here; tests/unit/aggregation-privacy.test.ts
// and the live random-week test difference every pair of levels.

export const K_MIN = 5;

export function suppressCount(n: number): number | null {
  return n > 0 && n < K_MIN ? null : n;
}

export function publishDirectionPair(
  ab: number,
  ba: number,
  complete: boolean
): { AB: number | null; BA: number | null } {
  if (!complete || suppressCount(ab) === null || suppressCount(ba) === null) {
    return { AB: null, BA: null };
  }
  return { AB: ab, BA: ba };
}

/** Sum of the published cells, and whether any cell was hidden. */
export function publishedTotal(cells: Iterable<number | null>): {
  total: number;
  hasHidden: boolean;
} {
  let total = 0;
  let hasHidden = false;
  for (const cell of cells) {
    if (cell === null) hasHidden = true;
    else total += cell;
  }
  return { total, hasHidden };
}

/** Raw totals of one base cell: one street, one class, one 15-min window. */
export interface RawCell {
  count: number;
  rows: number;
  directionalRows: number;
  ab: number;
  ba: number;
  speedSum: number; // sum of speed x count over rows that carry a speed
  speedCount: number;
}

export function emptyRawCell(): RawCell {
  return { count: 0, rows: 0, directionalRows: 0, ab: 0, ba: 0, speedSum: 0, speedCount: 0 };
}

/** Published base cells of one class, summed into a coarser bucket or window. */
export interface CellFold {
  count: number;
  hidden: boolean;
  ab: number;
  ba: number;
  pairHidden: boolean;
  directional: boolean;
  speedSum: number;
  speedCount: number;
}

export function emptyFold(): CellFold {
  return {
    count: 0, hidden: false, ab: 0, ba: 0, pairHidden: false, directional: false,
    speedSum: 0, speedCount: 0,
  };
}

/** Apply rules 1 and 2 to one base cell and add what it publishes (rule 3). */
export function foldCell(acc: CellFold, cell: RawCell): void {
  const count = suppressCount(cell.count);
  if (count === null) acc.hidden = true;
  else acc.count += count;
  acc.directional ||= cell.directionalRows > 0;
  const pair = publishDirectionPair(cell.ab, cell.ba, cell.directionalRows === cell.rows);
  if (pair.AB === null || pair.BA === null) acc.pairHidden = true;
  else {
    acc.ab += pair.AB;
    acc.ba += pair.BA;
  }
  if (cell.count >= K_MIN && cell.speedCount >= K_MIN) {
    acc.speedSum += cell.speedSum;
    acc.speedCount += cell.speedCount;
  }
}

/**
 * A coarser count: the sum of the published base cells. Nothing published
 * but something hidden reads as hidden, not as 0 (a single hidden base cell
 * stays null at every level).
 */
export function publishedSum(sum: number, hidden: boolean): number | null {
  return hidden && sum === 0 ? null : suppressCount(sum);
}

/** The numbers a fold publishes. */
export function publishFold(acc: CellFold): {
  count: number | null;
  AB: number | null;
  BA: number | null;
  speed: number | null;
} {
  const pairShown = !acc.pairHidden;
  return {
    count: publishedSum(acc.count, acc.hidden),
    AB: pairShown ? acc.ab : null,
    BA: pairShown ? acc.ba : null,
    speed: acc.speedCount >= K_MIN ? acc.speedSum / acc.speedCount : null,
  };
}
