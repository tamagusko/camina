export default function AdminAuditPage() {
  return (
    <section>
      <h1 className="text-section">Audit log</h1>
      <p className="text-body text-body-gray mt-2">
        Every admin mutation that touches sensor GPS, coverage, or config is
        recorded here with actor, action, target, and timestamp.
      </p>
      <p className="text-caption text-muted-gray mt-6">
        Backed by <code>audit_log</code> once the live DB is wired (Step D9).
      </p>
    </section>
  );
}
