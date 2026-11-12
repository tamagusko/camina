// Dublin-local time formatting. CAMINA v1 is Dublin-only, so timestamps must
// render in Europe/Dublin regardless of the viewer's own timezone.

const TIME_ZONE = "Europe/Dublin";

const timeHm = new Intl.DateTimeFormat("en-IE", {
  timeZone: TIME_ZONE,
  hour: "2-digit",
  minute: "2-digit",
});

const dateTime = new Intl.DateTimeFormat("en-IE", {
  timeZone: TIME_ZONE,
  dateStyle: "medium",
  timeStyle: "short",
});

/** Hour:minute in Dublin time (e.g. chart axis ticks). */
export function formatDublinTime(value: string | number | Date): string {
  return timeHm.format(new Date(value));
}

/** Date + short time in Dublin time (e.g. last-heartbeat display). */
export function formatDublinDateTime(value: string | number | Date): string {
  return dateTime.format(new Date(value));
}

const dayKey = new Intl.DateTimeFormat("en-CA", { timeZone: TIME_ZONE, year: "numeric", month: "2-digit", day: "2-digit" });
const dayMonth = new Intl.DateTimeFormat("en-IE", { timeZone: TIME_ZONE, day: "numeric", month: "short" });

/** "HH:mm" when `value` is on the same Dublin day as `now`, else "d MMM HH:mm". */
export function formatDublinUpdated(value: string | number | Date, now: Date = new Date()): string {
  const time = formatDublinTime(value);
  return dayKey.format(new Date(value)) === dayKey.format(now) ? time : `${dayMonth.format(new Date(value))} ${time}`;
}
