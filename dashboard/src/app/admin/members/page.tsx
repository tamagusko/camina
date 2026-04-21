export default function AdminMembersPage() {
  return (
    <section>
      <h1 className="text-section">Members</h1>
      <p className="text-body text-body-gray mt-2">
        Google sign-in allow list (email + role).
      </p>
      <p className="text-caption text-muted-gray mt-6">
        Dev allowlist is configured via <code>CAMINA_DEV_ALLOWED_EMAILS</code> in
        <code>.env.local</code>. Live DB-backed allowlist lands with Step D9.
      </p>
    </section>
  );
}
