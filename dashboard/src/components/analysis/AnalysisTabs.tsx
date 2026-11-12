import Link from "next/link";
import { cn } from "@/lib/cn";

type Tab = "compare" | "speed";

interface Props {
  city: string;
  street: string;
  window: string;
  active: Tab;
}

const TABS: { tab: Tab; label: string; path: string }[] = [
  { tab: "compare", label: "Compare roads", path: "analysis" },
  { tab: "speed", label: "Speed", path: "analysis/speed" },
];

/** The analyses of one road, side by side; switching keeps the road and period. */
export function AnalysisTabs({ city, street, window, active }: Props) {
  const query = new URLSearchParams({ street, window }).toString();
  return (
    <nav aria-label="Analyses" className="mt-4 flex gap-6 border-b border-[var(--line)] print:hidden">
      {TABS.map(({ tab, label, path }) => (
        <Link
          key={tab}
          href={`/${city}/${path}?${query}` as never}
          aria-current={tab === active ? "page" : undefined}
          className={cn(
            "-mb-px inline-flex min-h-11 items-center border-b-2 text-sm",
            tab === active
              ? "border-[var(--ink-1)] font-semibold text-[var(--ink-1)]"
              : "border-transparent text-[var(--ink-2)] hover:text-[var(--ink-1)]",
          )}
        >
          {label}
        </Link>
      ))}
    </nav>
  );
}
