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
