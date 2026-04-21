"use client";
import { cn } from "@/lib/cn";
import type { TimeWindow } from "@/lib/types";

const OPTIONS: { value: TimeWindow; label: string }[] = [
  { value: "now", label: "Now" },
  { value: "1h", label: "1 h" },
  { value: "24h", label: "24 h" },
  { value: "7d", label: "7 d" },
];

interface Props {
  value: TimeWindow;
  onChange: (w: TimeWindow) => void;
}

export function TimeWindowPicker({ value, onChange }: Props) {
  return (
    <div
      role="tablist"
      aria-label="Time window"
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
              "rounded-pill px-3 py-2 text-caption font-medium",
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
