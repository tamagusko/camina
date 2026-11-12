// Speeds against a limit: the figures of the speed page, from summed speed
// histograms of published cells (src/lib/privacy.ts). Shared by the mock and
// live repositories, so both publish the same numbers the same way.
import { K_MIN, SPEED_BIN_EDGES, emptyHistogram, v85FromHistogram } from "./privacy";
import { MOTOR_CLASSES, ROAD_USER_CLASSES, type RoadUserClass, type SpeedFigures } from "./types";

/** What the speed page looks at: one class, or all motor vehicles pooled. */
export type SpeedFocus = RoadUserClass | "motor";

export const SPEED_LIMIT_OPTIONS = [20, 30, 40, 50, 60, 80, 100, 120] as const;

/** Summed speeds of published cells: one class, over the window, one hour of
 *  the day, or one hour of one weekday. */
export interface SpeedFold {
  cls: RoadUserClass;
  hour: number | null; // Dublin hour of the day, 0..23; null for the whole window
  dow?: number | null; // Dublin weekday, 0 = Monday .. 6 = Sunday; with an hour
  hist: number[];
  speedSum: number;
  speedCount: number;
}

export interface SpeedResult {
  byClass: Partial<Record<RoadUserClass, SpeedFigures>>;
  focus: SpeedFigures;
  byHour: SpeedFigures[]; // 24 hours of the day, for the focus
  week: SpeedFigures[][]; // 7 weekdays (Monday first) × 24 hours, for the focus
}

/** Road users at or above `kmh`: whole bins from its edge up, and a linear
 *  share of the bin it falls inside (every Irish limit is a bin edge). Null
 *  inside the open top bin, where the speeds are not known. */
export function countAtOrAbove(hist: readonly number[], kmh: number): number | null {
  const top = SPEED_BIN_EDGES[SPEED_BIN_EDGES.length - 1]!;
  if (kmh > top) return null;
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
const passes = (n: number) => n === 0 || n >= K_MIN;

function split(over: number | null, timed: number): number | null {
  return over !== null && passes(over) && passes(timed - over) ? over : null;
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

type Split = "overLimit" | "overBy10";
const SHARE: Record<Split, "overLimitShare" | "overBy10Share"> = { overLimit: "overLimitShare", overBy10: "overBy10Share" };

/** Complementary suppression of a split. The children partition the parent,
 *  so the parent minus the shown children gives the sum of the hidden ones:
 *  a lone hidden child would be given away. Siblings are hidden, smallest
 *  first, until the hidden ones together pass the k-floor. Applied whether or
 *  not the parent is shown, since a hidden parent can be derived one level up.
 *  Needs the unrounded counts, so it runs on the true splits (`truth`). */
function protect(children: SpeedFigures[], truth: (number | null)[], key: Split): SpeedFigures[] {
  const hidden = new Set(children.flatMap((c, i) => (c.timed !== null && c[key] === null ? [i] : [])));
  if (hidden.size === 0) return children;
  const aggregate = () => {
    let over = 0, timed = 0;
    for (const i of hidden) { over += truth[i] ?? 0; timed += children[i]!.timed!; }
    return passes(over) && passes(timed - over);
  };
  const shown = children
    .map((c, i) => ({ i, timed: c.timed }))
    .filter(({ i, timed }) => timed !== null && !hidden.has(i))
    .sort((a, b) => a.timed! - b.timed! || a.i - b.i);
  while (!aggregate() && shown.length) hidden.add(shown.shift()!.i);
  return children.map((c, i) => (hidden.has(i) ? { ...c, [key]: null, [SHARE[key]]: null } : c));
}

function protectBoth(children: SpeedFigures[], hists: number[][], limitKmh: number | null): SpeedFigures[] {
  if (limitKmh === null) return children;
  const truth = (kmh: number) => hists.map((h) => countAtOrAbove(h, kmh));
  return protect(protect(children, truth(limitKmh), "overLimit"), truth(limitKmh + 10), "overBy10");
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

/** The speed page's figures from the folds of one road and window. Every
 *  group that partitions a published figure is protected against it: motor
 *  classes against all motor vehicles, hours against the window, and the
 *  weekdays of an hour against that hour. */
export function speedResult(folds: SpeedFold[], focus: SpeedFocus, limitKmh: number | null): SpeedResult {
  const inFocus = new Set<RoadUserClass>(focusClasses(focus));
  const group = (subsets: SpeedFold[][]) => {
    const pools = subsets.map(pooled);
    const figures = pools.map((p) => speedFigures(p.hist, p.speedSum, p.speedCount, limitKmh));
    return protectBoth(figures, pools.map((p) => p.hist), limitKmh);
  };
  const whole = folds.filter((f) => f.hour === null);
  const hourly = folds.filter((f) => f.hour !== null && (f.dow ?? null) === null && inFocus.has(f.cls));
  const cells = folds.filter((f) => f.hour !== null && (f.dow ?? null) !== null && inFocus.has(f.cls));

  const byClass: SpeedResult["byClass"] = {};
  const present = ROAD_USER_CLASSES.filter((cls) => whole.some((f) => f.cls === cls));
  const motor = present.filter((cls) => (MOTOR_CLASSES as readonly RoadUserClass[]).includes(cls));
  group(motor.map((cls) => whole.filter((f) => f.cls === cls))).forEach((f, i) => { byClass[motor[i]!] = f; });
  // No pool of the other classes is published: nothing to protect them against.
  for (const cls of present.filter((c) => !motor.includes(c))) byClass[cls] = group([whole.filter((f) => f.cls === cls)])[0];

  const hours = Array.from({ length: 24 }, (_, hour) => hour);
  const days = Array.from({ length: 7 }, (_, dow) => dow);
  const byDay = hours.map((hour) => group(days.map((dow) => cells.filter((f) => f.hour === hour && f.dow === dow))));
  return {
    byClass,
    focus: group([whole.filter((f) => inFocus.has(f.cls))])[0]!,
    byHour: group(hours.map((hour) => hourly.filter((f) => f.hour === hour))),
    week: days.map((dow) => hours.map((hour) => byDay[hour]![dow]!)),
  };
}
