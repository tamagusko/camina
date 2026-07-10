// Deployment-environment helper shared by the fail-closed gates
// (data source selection, OAuth allowlist, cron auth, admin route).

/** True when running (or building) for a production deployment. */
export function isProduction(): boolean {
  return (
    process.env.VERCEL_ENV === "production" ||
    process.env.NODE_ENV === "production"
  );
}
