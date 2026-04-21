import { isMock } from "@/lib/data-source";
import { loadSensors } from "@/lib/mock-loader";

export default async function AdminSensorsPage() {
  const sensors = isMock ? await loadSensors() : [];
  return (
    <section>
      <h1 className="text-section">Sensors</h1>
      <p className="text-body text-body-gray mt-2">
        Register, edit, and map sensors to streets. GPS is admin-only and never
        leaves this console.
      </p>
      <table className="mt-8 w-full border-collapse text-caption">
        <thead>
          <tr className="border-b border-chip-gray text-left">
            <th className="py-3">ID</th>
            <th className="py-3">Display name</th>
            <th className="py-3">Config v.</th>
            <th className="py-3">Last heartbeat</th>
          </tr>
        </thead>
        <tbody>
          {sensors.map((s) => (
            <tr key={s.id} className="border-b border-chip-gray">
              <td className="py-3 font-mono">{s.id}</td>
              <td className="py-3">{s.display_name}</td>
              <td className="py-3 font-mono">{s.config_version}</td>
              <td className="py-3 text-body-gray">{s.last_heartbeat ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
