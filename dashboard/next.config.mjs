// NEXT_PUBLIC_CAMINA_DEV_ADMIN bypasses admin auth in the dev UI. It is
// inlined into the client bundle at build time, so it must never be present
// when building for a production deployment. Keyed on VERCEL_ENV only:
// `next build` always sets NODE_ENV=production, so gating on NODE_ENV would
// block every local/CI build where the flag legitimately sits in .env.local.
if (
  process.env.VERCEL_ENV === "production" &&
  process.env.NEXT_PUBLIC_CAMINA_DEV_ADMIN
) {
  throw new Error(
    "NEXT_PUBLIC_CAMINA_DEV_ADMIN is set while building for production. " +
      "It bypasses admin auth and must not ship. Remove the variable from " +
      "the Vercel project environment (or your shell) and rebuild."
  );
}

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Strict Mode double-mounts effects in dev, which races with MapLibre's
  // canvas sizing (mount → cleanup → remount). Re-enable once the map init
  // is guarded with an isMounted ref and a ResizeObserver-driven resize.
  reactStrictMode: false,
  // cacheComponents: true,  // Re-enable once /[city] and /[city]/street/[slug]
  // wrap their uncached data reads in <Suspense> boundaries.
  typedRoutes: true,
  images: {
    remotePatterns: [],
  },
};

export default nextConfig;
