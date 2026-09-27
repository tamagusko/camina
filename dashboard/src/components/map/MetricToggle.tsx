"use client";
import { cn } from "@/lib/cn";
import type { MapMode } from "@/lib/geo";

const options: { value: MapMode; label: string }[] = [{ value: "counts", label: "Counts" }, { value: "usual", label: "vs usual" }, { value: "speed", label: "Speed" }];
interface Props { value: MapMode; onChange: (m: MapMode) => void; }
export function MetricToggle({ value, onChange }: Props) {
  return <div role="radiogroup" aria-label="Colour streets by" className="flex rounded-sm border border-line bg-surface p-1">
    {options.map((option, index) => <button key={option.value} role="radio" aria-checked={value === option.value} tabIndex={value === option.value ? 0 : -1}
      onKeyDown={(event) => { if (["ArrowRight", "ArrowLeft"].includes(event.key)) { event.preventDefault(); const next = options[(index + (event.key === "ArrowRight" ? 1 : options.length - 1)) % options.length]!; onChange(next.value); (event.currentTarget.parentElement?.children[[...options].indexOf(next)] as HTMLElement)?.focus(); } }}
      onClick={() => onChange(option.value)} className={cn("min-h-11 flex-1 whitespace-nowrap rounded-sm px-3 text-sm", value === option.value ? "bg-accent text-bg" : "text-ink-1 hover:opacity-70")}>{option.label}</button>)}
  </div>;
}
