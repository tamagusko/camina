import type { ReactNode } from "react";
import { Bike, Bus, Car, PersonStanding, Truck, type LucideIcon } from "lucide-react";
import type { RoadUserClass } from "@/lib/types";

// Lucide has no e-scooter, SUV, motorbike or van: these four are drawn in its
// style (24 grid, 2 px round strokes) so the set reads as one family.
function Drawn({ size, children }: { size: number; children: ReactNode }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {children}
    </svg>
  );
}

const DRAWN: Partial<Record<RoadUserClass, ReactNode>> = {
  "e-scooter": <><circle cx="5" cy="18" r="2" /><circle cx="19" cy="18" r="2" /><path d="M7 18h10l-2-13" /><path d="M13 5h4" /></>,
  SUV: <><path d="M3 17V11l2-5h11l3 5h2v6" /><path d="M9 17h6" /><path d="M5 11h14" /><circle cx="7" cy="17" r="2" /><circle cx="17" cy="17" r="2" /></>,
  motorcyclist: <><circle cx="5" cy="17" r="3" /><circle cx="19" cy="17" r="3" /><path d="M8 17h5l3-6h-6l-2 3" /><path d="M16 11l-1-4h3" /></>,
  delivery_van: <><path d="M3 17V7h11v10" /><path d="M14 10h4l3 3v4h-2" /><path d="M9 17h6" /><circle cx="7" cy="17" r="2" /><circle cx="17" cy="17" r="2" /></>,
};

const LUCIDE: Partial<Record<RoadUserClass, LucideIcon>> = {
  person: PersonStanding,
  cyclist: Bike,
  car: Car,
  bus: Bus,
  truck: Truck,
};

/** A small decorative icon beside a class name; the name carries the meaning. */
export function ClassIcon({ cls, size = 16 }: { cls: RoadUserClass; size?: number }) {
  const Icon = LUCIDE[cls];
  if (Icon) return <Icon size={size} aria-hidden="true" />;
  return <Drawn size={size}>{DRAWN[cls]}</Drawn>;
}
