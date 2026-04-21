"use client";
import { cn } from "@/lib/cn";

interface Props {
  ramp: readonly string[];
  min: number;
  max: number;
  unit: string;
  className?: string;
}

export function ColourLegend({ ramp, min, max, unit, className }: Props) {
  const gradient = `linear-gradient(90deg, ${ramp.join(", ")})`;
  return (
    <div
      className={cn(
        "rounded-card bg-white/95 p-3 shadow-subtle backdrop-blur",
        className
      )}
    >
      <div
        className="h-2 w-40 rounded-pill"
        style={{ backgroundImage: gradient }}
        aria-label={`Colour scale from ${min} to ${max} ${unit}`}
      />
      <div className="mt-1 flex justify-between text-micro text-body-gray">
        <span>
          {min.toLocaleString()} {unit}
        </span>
        <span>
          {max.toLocaleString()} {unit}
        </span>
      </div>
    </div>
  );
}
