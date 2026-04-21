export default function AdminEventsPage() {
  return (
    <section>
      <h1 className="text-section">Events</h1>
      <p className="text-body text-body-gray mt-2">
        Silent sensors, reconciliation failures, config-apply errors.
      </p>
      <p className="text-caption text-muted-gray mt-6">
        Populated by the cron jobs under <code>/api/cron/*</code> once the live
        database is connected (Step D12).
      </p>
    </section>
  );
}
