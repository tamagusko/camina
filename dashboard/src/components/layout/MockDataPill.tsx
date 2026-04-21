import { Pill } from "@/components/ui/pill";
import { isMock } from "@/lib/data-source";

// Persistent indicator that the view is backed by mock fixtures rather than
// live ingest. Hidden entirely when CAMINA_DATA_SOURCE=live.
export function MockDataPill() {
  if (!isMock) return null;
  return (
    <div
      className="pointer-events-none fixed top-3 left-1/2 z-50 -translate-x-1/2"
      aria-live="polite"
    >
      <Pill variant="mock">Mock data · Dublin demo</Pill>
    </div>
  );
}
