"use client";
import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { Pill } from "@/components/ui/pill";
import { cn } from "@/lib/cn";
import { ROAD_USER_CLASSES, type RoadUserClass } from "@/lib/types";

interface Props {
  selected: RoadUserClass[];
  onChange: (next: RoadUserClass[]) => void;
}

export function ClassFilter({ selected, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const allSelected = selected.length === ROAD_USER_CLASSES.length;

  function toggle(c: RoadUserClass) {
    onChange(selected.includes(c) ? selected.filter((x) => x !== c) : [...selected, c]);
  }

  return (
    <div className="relative">
      <button
        className="chip gap-2"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        {allSelected ? "All classes" : `${selected.length} classes`}
        <ChevronDown className="h-4 w-4" />
      </button>
      {open && (
        <div
          role="menu"
          className="absolute right-0 z-10 mt-2 w-56 rounded-card bg-white p-1 shadow-subtle"
        >
          {ROAD_USER_CLASSES.map((c) => {
            const on = selected.includes(c);
            return (
              <button
                key={c}
                role="menuitemcheckbox"
                aria-checked={on}
                onClick={() => toggle(c)}
                className={cn(
                  "flex w-full items-center justify-between rounded-card px-3 py-2 text-caption",
                  on ? "bg-chip-gray text-black" : "text-black hover:bg-hover-light"
                )}
              >
                <span className="capitalize">{c.replace("_", " ")}</span>
                <span className="h-3 w-3 rounded-full border border-black bg-transparent">
                  {on && <span className="block h-full w-full rounded-full bg-black" />}
                </span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
