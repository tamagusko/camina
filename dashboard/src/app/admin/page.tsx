import { dataSource } from "@/lib/data-source";

export default function AdminHome() {
  return (
    <section>
      <h1 className="text-section">Overview</h1>
      <p className="text-body text-body-gray mt-2">
        Data source: <strong>{dataSource}</strong>
      </p>
      <ul className="mt-6 grid gap-3 md:grid-cols-2 lg:grid-cols-3">
        <li className="card p-6">
          <h2 className="text-sub">Sensors</h2>
          <p className="text-caption text-body-gray mt-2">
            Register, edit, and map sensors to streets.
          </p>
        </li>
        <li className="card p-6">
          <h2 className="text-sub">Events</h2>
          <p className="text-caption text-body-gray mt-2">
            Silent sensors, reconciliation mismatches, config-apply failures.
          </p>
        </li>
        <li className="card p-6">
          <h2 className="text-sub">Audit</h2>
          <p className="text-caption text-body-gray mt-2">
            Who changed what and when.
          </p>
        </li>
      </ul>
    </section>
  );
}
