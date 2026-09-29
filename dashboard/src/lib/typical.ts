// "Compared with usual": a window's published total against the same window in
// the previous weeks. Built from published values only (src/lib/privacy.ts),
// so it reveals nothing the counts do not. Past weeks are exactly 7 × 24 h back,
// so for a few weeks after a clock change "now" is compared with the hour next
// to it; accepted, it heals itself.

export const TYPICAL_WEEKS = 4;
export const TYPICAL_MIN_WEEKS = 2;
/** Below this usual total a ratio is noise (2 vs 1 is "twice as busy"). */
const MIN_USUAL = 20;

/** A window's published total and how many 15-min cells had any reading. */
export interface WindowTotal {
  total: number;
  cells: number;
}

/** Usual total for the current window: the past weeks' rate per 15-min cell,
 *  times the cells the current window has, so an outage on either side does
 *  not read as a quiet street. Null without enough history. */
export function typicalTotal(current: WindowTotal, past: WindowTotal[]): number | null {
  const used = past.filter((week) => week.cells > 0);
  if (used.length < TYPICAL_MIN_WEEKS || current.cells === 0) return null;
  const total = used.reduce((sum, week) => sum + week.total, 0);
  const cells = used.reduce((sum, week) => sum + week.cells, 0);
  return (total / cells) * current.cells;
}

export const USUAL_LEVELS = ["much-lower", "lower", "usual", "higher", "much-higher"] as const;
export type UsualLevel = (typeof USUAL_LEVELS)[number];

export const USUAL_LABEL: Record<UsualLevel, string> = {
  "much-lower": "Much quieter",
  lower: "Quieter",
  usual: "Usual",
  higher: "Busier",
  "much-higher": "Much busier",
};

/** Symmetric steps: ×0.8–×1.25 is usual, beyond ×0.5 or ×2 is "much". */
export function usualLevel(value: number | null, typical: number | null): UsualLevel | null {
  if (value === null || typical === null || typical < MIN_USUAL) return null;
  const ratio = value / typical;
  if (ratio < 0.5) return "much-lower";
  if (ratio < 0.8) return "lower";
  if (ratio <= 1.25) return "usual";
  if (ratio <= 2) return "higher";
  return "much-higher";
}
