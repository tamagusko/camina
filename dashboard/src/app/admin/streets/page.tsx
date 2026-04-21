export default function AdminStreetsPage() {
  return (
    <section>
      <h1 className="text-section">Streets</h1>
      <p className="text-body text-body-gray mt-2">
        Manage the public street catalogue (name, geometry, active toggle).
      </p>
      <p className="text-caption text-muted-gray mt-6">
        Implementation pending — depends on Drizzle / PostGIS wiring (Step D9).
      </p>
    </section>
  );
}
