import { and, desc, eq, isNotNull } from "drizzle-orm";
import { isLive } from "@/lib/data-source";
import { db } from "@/lib/db";
import { sensorDailyTotals } from "../../../../drizzle/schema";

export default async function AdminEventsPage() {
  const events = isLive
    ? await db()
        .select({
          sensorId: sensorDailyTotals.sensorId,
          day: sensorDailyTotals.day,
          mismatch: sensorDailyTotals.mismatchJson,
        })
        .from(sensorDailyTotals)
        .where(and(eq(sensorDailyTotals.reconciled, false), isNotNull(sensorDailyTotals.mismatchJson)))
        .orderBy(desc(sensorDailyTotals.day))
        .limit(100)
    : [];
  return (
    <section>
      <h1 className="text-section">Events</h1>
      <p className="text-body text-body-gray mt-2">
        Silent sensors, reconciliation failures, config-apply errors.
      </p>
      {events.length === 0 ? (
        <p className="text-caption text-muted-gray mt-6">No reconciliation mismatches.</p>
      ) : (
        <ul className="mt-6 space-y-4">
          {events.map((event) => (
            <li key={`${event.sensorId}-${event.day}`}>
              <p className="text-body">{event.sensorId} · {event.day}</p>
              <pre className="text-caption text-muted-gray mt-1 whitespace-pre-wrap">
                {JSON.stringify(event.mismatch, null, 2)}
              </pre>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
