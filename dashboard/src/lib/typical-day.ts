// Average road users per hour of the day, weekdays and weekends apart, from
// hourly readings. Offline hours and hidden values are left out, as elsewhere.
import { ROAD_USER_CLASSES, type RoadUserClass, type StreetReading } from "./types";

export interface TypicalHour {
  hour: number;
  weekday: number | null;
  weekend: number | null;
}

const dublinParts = new Intl.DateTimeFormat("en-GB", {
  timeZone: "Europe/Dublin",
  weekday: "short",
  hour: "2-digit",
  hourCycle: "h23",
});

function dublinHour(iso: string): { hour: number; weekend: boolean } {
  const parts = dublinParts.formatToParts(new Date(iso));
  const day = parts.find((p) => p.type === "weekday")?.value;
  return { hour: Number(parts.find((p) => p.type === "hour")?.value), weekend: day === "Sat" || day === "Sun" };
}

function valueOf(row: StreetReading, cls: RoadUserClass | null): number | null {
  if (cls) return row.counts[cls];
  return ROAD_USER_CLASSES.reduce((sum, c) => sum + (row.counts[c] ?? 0), 0);
}

export function typicalDay(readings: StreetReading[], cls: RoadUserClass | null): TypicalHour[] {
  const sums = Array.from({ length: 24 }, () => ({ weekday: { sum: 0, n: 0 }, weekend: { sum: 0, n: 0 } }));
  for (const row of readings) {
    if (row.missing) continue;
    const value = valueOf(row, cls);
    if (value === null) continue;
    const { hour, weekend } = dublinHour(row.bucket);
    const acc = sums[hour]![weekend ? "weekend" : "weekday"];
    acc.sum += value;
    acc.n += 1;
  }
  const mean = ({ sum, n }: { sum: number; n: number }) => (n ? sum / n : null);
  return sums.map((s, hour) => ({ hour, weekday: mean(s.weekday), weekend: mean(s.weekend) }));
}
