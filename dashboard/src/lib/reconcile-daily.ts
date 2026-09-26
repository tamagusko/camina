import "server-only";
import { and, countDistinct, eq, gte, lt, sql } from "drizzle-orm";
import { db } from "@/lib/db";
import { sensorDailyTotals, sensorReadings } from "../../drizzle/schema";

type Db = ReturnType<typeof db>;

interface ClassDifference {
  daily: number;
  windows: number;
  difference: number;
}

export interface DailyMismatch {
  classes: Record<string, ClassDifference>;
  windowCount?: ClassDifference;
}

export function buildDailyMismatch(
  dailyTotals: Record<string, number>,
  windowTotals: Record<string, number>,
  observedWindowCount: number,
  reportedWindowCount: number
): DailyMismatch | null {
  const classes: Record<string, ClassDifference> = {};
  const classNames = [...new Set([...Object.keys(dailyTotals), ...Object.keys(windowTotals)])].sort();
  for (const className of classNames) {
    const daily = dailyTotals[className] ?? 0;
    const windows = windowTotals[className] ?? 0;
    if (daily !== windows) classes[className] = { daily, windows, difference: windows - daily };
  }
  const mismatch: DailyMismatch = { classes };
  if (observedWindowCount !== reportedWindowCount) {
    mismatch.windowCount = {
      daily: reportedWindowCount,
      windows: observedWindowCount,
      difference: observedWindowCount - reportedWindowCount,
    };
  }
  return Object.keys(classes).length > 0 || mismatch.windowCount ? mismatch : null;
}

function utcDayBounds(day: string): { start: Date; end: Date } {
  const start = new Date(`${day}T00:00:00.000Z`);
  const end = new Date(start.getTime() + 24 * 60 * 60 * 1000);
  return { start, end };
}

export function yesterdayUtc(now: Date = new Date()): string {
  return new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() - 1))
    .toISOString()
    .slice(0, 10);
}

export async function reconcileDay(
  day: string = yesterdayUtc(),
  database: Db = db()
): Promise<{ checked: number; mismatched: number; day: string }> {
  const dailyRows = await database
    .select({
      sensorId: sensorDailyTotals.sensorId,
      totalsJson: sensorDailyTotals.totalsJson,
      windowCount: sensorDailyTotals.windowCount,
    })
    .from(sensorDailyTotals)
    .where(eq(sensorDailyTotals.day, day));
  const { start, end } = utcDayBounds(day);
  let mismatched = 0;

  for (const daily of dailyRows) {
    const windowRows = await database
      .select({
        className: sensorReadings.className,
        total: sql<number>`coalesce(sum(${sensorReadings.count}), 0)::integer`,
      })
      .from(sensorReadings)
      .where(
        and(
          eq(sensorReadings.sensorId, daily.sensorId),
          gte(sensorReadings.windowStart, start),
          lt(sensorReadings.windowStart, end)
        )
      )
      .groupBy(sensorReadings.className);
    const [windowCountRow] = await database
      .select({ windowCount: countDistinct(sensorReadings.windowStart) })
      .from(sensorReadings)
      .where(
        and(
          eq(sensorReadings.sensorId, daily.sensorId),
          gte(sensorReadings.windowStart, start),
          lt(sensorReadings.windowStart, end)
        )
      );
    const totals = Object.fromEntries(windowRows.map((row) => [row.className, Number(row.total)]));
    const observedWindows = Number(windowCountRow?.windowCount ?? 0);
    const reportedTotals = daily.totalsJson as Record<string, number>;
    const mismatch = buildDailyMismatch(reportedTotals, totals, observedWindows, daily.windowCount);
    if (mismatch) mismatched += 1;
    await database
      .update(sensorDailyTotals)
      .set({ reconciled: mismatch === null, mismatchJson: mismatch })
      .where(and(eq(sensorDailyTotals.sensorId, daily.sensorId), eq(sensorDailyTotals.day, day)));
  }
  return { checked: dailyRows.length, mismatched, day };
}
