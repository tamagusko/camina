// Typed factory for Next.js cache tags. Using explicit functions instead of
// string literals prevents typos and lets `revalidateTag` invalidations stay
// in sync with `cacheTag` declarations.

export const tags = {
  streetsList: (city: string) => `streets:list:${city}` as const,
  street: (id: string) => `street:${id}` as const,
  streetReadings: (id: string, metric: string, window: string) =>
    `street:${id}:readings:${metric}:${window}` as const,
  cityMetrics: (city: string, metric: string, window: string) =>
    `city:${city}:metrics:${metric}:${window}` as const,
};

export type StreetTag = ReturnType<typeof tags.street>;
