// Public-read privacy rules, shared by the mock and live adapters.
//
// 1. k-floor: a published count is 0 or >= K_MIN. Counts of 1..K_MIN-1 are
//    re-identifiable and are published as null.
// 2. Direction pairs: AB + BA = count, so one hidden cell next to a shown cell
//    and a shown count is recoverable by subtraction. If either cell of a class
//    is hidden, both are hidden. A pair is also hidden when the class's
//    direction data does not cover every row in the bucket (mixed schema 1.0
//    and 1.1 rows), since count - AB - BA would then expose the undirected rest.
// 3. Totals: a number is published only if it is the sum of the published
//    numbers beneath it. A street total is the sum of the published class
//    counts, with `hasHidden` set when any cell was hidden. It is never the true total,
//    because true total - shown cells = the hidden cell. Suppressing extra
//    cells instead would hide large, useful counts, and would still leak across
//    two requests with different class filters; a sum of published cells
//    carries no information about hidden cells in any combination of requests.
//
// docs/PROTOCOL.md section 4.1 points here.

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
