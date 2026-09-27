// Sharing and the printed street report.
import type { StreetReading } from "./types";

/** End of the last bucket with published data (ISO), or null if there is none. */
export function dataUpdatedAt(readings: StreetReading[], bucketMinutes: number): string | null {
  const last = [...readings].reverse().find((r) => !r.missing);
  return last ? new Date(Date.parse(last.bucket) + bucketMinutes * 60_000).toISOString() : null;
}

/** Fallback share targets for browsers without the Web Share API. */
export function shareLinks(title: string, url: string): { whatsapp: string; linkedin: string; email: string } {
  return {
    whatsapp: `https://wa.me/?text=${encodeURIComponent(`${title} ${url}`)}`,
    // LinkedIn takes only the URL; the post preview comes from the page's metadata.
    linkedin: `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(url)}`,
    email: `mailto:?subject=${encodeURIComponent(title)}&body=${encodeURIComponent(url)}`,
  };
}
