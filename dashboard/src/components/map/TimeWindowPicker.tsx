"use client";
import { cn } from "@/lib/cn";
import type { TimeWindow } from "@/lib/types";
const options: { value: TimeWindow; label: string }[] = [{ value: "now", label: "Now" }, { value: "24h", label: "24 h" }, { value: "7d", label: "7 d" }];
interface Props { value: TimeWindow; onChange: (w: TimeWindow) => void; }
export function TimeWindowPicker({ value, onChange }: Props) {
  return <div role="radiogroup" aria-label="Time window" className="inline-flex rounded-sm border border-line bg-surface p-1">
    {options.map((option, index) => <button key={option.value} role="radio" aria-checked={value === option.value} tabIndex={value === option.value ? 0 : -1}
      onKeyDown={(event) => { if (["ArrowRight", "ArrowLeft"].includes(event.key)) { event.preventDefault(); const next = options[(index + (event.key === "ArrowRight" ? 1 : options.length - 1)) % options.length]!; onChange(next.value); (event.currentTarget.parentElement?.children[options.indexOf(next)] as HTMLElement)?.focus(); } }}
      onClick={() => onChange(option.value)} className={cn("min-h-11 rounded-sm px-4 text-sm", value === option.value ? "bg-accent text-bg" : "text-ink-1 hover:opacity-70")}>{option.label}</button>)}
  </div>;
}
