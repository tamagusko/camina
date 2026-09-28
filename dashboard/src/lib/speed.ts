// Speeds against a limit: the figures of the speed page, from summed speed
// histograms of published cells (src/lib/privacy.ts). Shared by the mock and
// live repositories, so both publish the same numbers the same way.
import { K_MIN, SPEED_BIN_EDGES, emptyHistogram, v85FromHistogram } from "./privacy";
import { MOTOR_CLASSES, ROAD_USER_CLASSES, type RoadUserClass, type SpeedFigures } from "./types";

/** What the speed page looks at: one class, or all motor vehicles pooled. */
export type SpeedFocus = RoadUserClass | "motor";

export const SPEED_LIMIT_OPTIONS = [20, 30, 40, 50, 60, 80, 100, 120] as const;

/** Summed speeds of published cells: one class, over the window or one hour of the day. */
export interface SpeedFold {
  cls: RoadUserClass;
  hour: number | null; // Dublin hour of the day, 0..23; null for the whole window
  hist: number[];
  speedSum: number;
  speedCount: number;
}

export interface SpeedResult {
  byClass: Partial<Record<RoadUserClass, SpeedFigures>>;
  focus: SpeedFigures;
  byHour: SpeedFigures[]; // 24 hours of the day, for the focus
}

/** Road users at or above `kmh`: whole bins from its edge up, and a linear
 *  share of the bin it falls inside (every Irish limit is a bin edge). */
export function countAtOrAbove(hist: readonly number[], kmh: number): number {
  let n = 0;
  for (let bin = 0; bin < hist.length; bin++) {
    const lower = SPEED_BIN_EDGES[bin]!;
    const upper = SPEED_BIN_EDGES[bin + 1] ?? Infinity;
    if (lower >= kmh) n += hist[bin]!;
    else if (upper > kmh) n += hist[bin]! * ((upper - kmh) / (upper - lower));
  }
  return Math.round(n);
}

// k-floor on a split: both sides of "above / not above" are published only
// when each is 0 or at least K_MIN; otherwise the smaller side would count
// one to four people.
function split(over: number, timed: number): number | null {
  const under = timed - over;
  const ok = (n: number) => n === 0 || n >= K_MIN;
  return ok(over) && ok(under) ? over : null;
}

export function speedFigures(hist: readonly number[], speedSum: number, speedCount: number, limitKmh: number | null): SpeedFigures {
  const total = hist.reduce((s, n) => s + n, 0);
  const timed = total >= K_MIN ? total : null;
  const over = timed !== null && limitKmh !== null ? split(countAtOrAbove(hist, limitKmh), timed) : null;
  const over10 = timed !== null && limitKmh !== null ? split(countAtOrAbove(hist, limitKmh + 10), timed) : null;
  return {
    timed,
    meanKmh: speedCount >= K_MIN ? speedSum / speedCount : null,
    v85Kmh: v85FromHistogram(hist),
    overLimit: over,
    overLimitShare: over !== null && timed ? over / timed : null,
    overBy10: over10,
    overBy10Share: over10 !== null && timed ? over10 / timed : null,
  };
}

function pooled(folds: SpeedFold[]): { hist: number[]; speedSum: number; speedCount: number } {
  const hist = emptyHistogram();
  let speedSum = 0;
  let speedCount = 0;
  for (const f of folds) {
    f.hist.forEach((n, bin) => { hist[bin] = (hist[bin] ?? 0) + n; });
    speedSum += f.speedSum;
    speedCount += f.speedCount;
  }
  return { hist, speedSum, speedCount };
}

export function focusClasses(focus: SpeedFocus): readonly RoadUserClass[] {
  return focus === "motor" ? MOTOR_CLASSES : [focus];
}

/** The speed page's figures from the folds of one road and window. */
export function speedResult(folds: SpeedFold[], focus: SpeedFocus, limitKmh: number | null): SpeedResult {
  const inFocus = new Set<RoadUserClass>(focusClasses(focus));
  const figures = (subset: SpeedFold[]) => {
    const p = pooled(subset);
    return speedFigures(p.hist, p.speedSum, p.speedCount, limitKmh);
  };
  const whole = folds.filter((f) => f.hour === null);
  const byClass: SpeedResult["byClass"] = {};
  for (const cls of ROAD_USER_CLASSES) {
    const own = whole.filter((f) => f.cls === cls);
    if (own.length) byClass[cls] = figures(own);
  }
  return {
    byClass,
    focus: figures(whole.filter((f) => inFocus.has(f.cls))),
    byHour: Array.from({ length: 24 }, (_, hour) =>
      figures(folds.filter((f) => f.hour === hour && inFocus.has(f.cls)))),
  };
}
