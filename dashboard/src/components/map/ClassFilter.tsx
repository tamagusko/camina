"use client";
import { ROAD_USER_CLASSES, classLabel, type RoadUserClass } from "@/lib/types";

interface Props { selected: RoadUserClass | null; onChange: (next: RoadUserClass | null) => void; }

export function ClassFilter({ selected, onChange }: Props) {
  return (
    <select aria-label="Road user class" value={selected ?? ""} onChange={(e) => onChange(e.target.value ? e.target.value as RoadUserClass : null)}
      className="h-11 w-full min-w-0 rounded-sm border border-line bg-surface px-3 text-sm text-ink-1">
      <option value="">All road users</option>
      {ROAD_USER_CLASSES.map((c) => <option key={c} value={c}>{classLabel(c)}</option>)}
    </select>
  );
}
