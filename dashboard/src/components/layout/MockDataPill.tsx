import { Pill } from "@/components/ui/pill";
import { isMock } from "@/lib/data-source";

// Persistent indicator that the view is backed by mock fixtures rather than
// live ingest. Hidden entirely when CAMINA_DATA_SOURCE=live.
export function MockDataPill({ placement = "map" }: { placement?: "map" | "detail" }) {
  if (!isMock) return null;
  return (
    <div
      className={placement === "map"
        ? "pointer-events-none fixed top-[76px] left-1/2 z-20 -translate-x-1/2 md:top-3"
        : "pointer-events-none fixed right-4 top-3 z-20 md:right-auto md:left-1/2 md:-translate-x-1/2"}
      aria-live="polite"
    >
      <Pill variant="mock">Mock data · Dublin demo</Pill>
    </div>
  );
}
