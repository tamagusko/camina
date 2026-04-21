"use client";
import { Pill } from "@/components/ui/pill";
import { cn } from "@/lib/cn";
import type { Metric } from "@/lib/types";

interface Props {
  value: Metric;
  onChange: (m: Metric) => void;
}

const OPTIONS: { value: Metric; label: string }[] = [
  { value: "counts", label: "Counts" },
  { value: "speed", label: "Speed" },
];

export function MetricToggle({ value, onChange }: Props) {
  return (
    <div
      role="tablist"
      aria-label="Metric"
      className="inline-flex items-center gap-1 rounded-pill bg-chip-gray p-1"
    >
      {OPTIONS.map((opt) => {
        const active = opt.value === value;
        return (
          <button
            key={opt.value}
            role="tab"
            aria-selected={active}
            onClick={() => onChange(opt.value)}
            className={cn(
              "rounded-pill px-4 py-2 text-caption font-medium transition-none",
              active ? "bg-black text-white" : "text-black hover:bg-hover-light"
            )}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
