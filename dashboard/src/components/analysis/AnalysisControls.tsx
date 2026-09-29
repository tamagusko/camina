"use client";
import { usePathname, useRouter } from "next/navigation";
import { ROAD_USER_CLASSES, classLabel, type RoadUserClass } from "@/lib/types";
import { WINDOW_LABEL, type AnalysisWindow } from "@/lib/analysis";

interface Props {
  streets: { id: string; displayName: string }[];
  street: string;
  vs: string; // "city" or a street id
  window: AnalysisWindow;
  cls: RoadUserClass | null;
}

const SELECT = "h-11 w-full min-w-0 rounded-sm border border-[var(--line)] bg-[var(--surface)] px-3 text-sm text-[var(--ink-1)]";

/** Four selects; each change is a new URL, so every comparison can be shared. */
export function AnalysisControls({ streets, street, vs, window, cls }: Props) {
  const router = useRouter();
  const pathname = usePathname();
  const set = (key: string, value: string) => {
    const next = new URLSearchParams({ street, vs, window, ...(cls ? { class: cls } : {}) });
    if (value) next.set(key, value);
    else next.delete(key);
    // Comparing a road with itself says nothing: fall back to the city.
    if (key === "street" && next.get("vs") === value) next.set("vs", "city");
    router.replace(`${pathname}?${next.toString()}` as never, { scroll: false });
  };
  const sorted = [...streets].sort((a, b) => a.displayName.localeCompare(b.displayName));
  const field = (label: string, control: React.ReactNode) => (
    <label className="flex min-w-0 flex-col gap-1 text-xs text-[var(--ink-2)]">{label}{control}</label>
  );
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4 print:hidden">
      {field("Road", <select className={SELECT} value={street} onChange={(e) => set("street", e.target.value)}>
        {sorted.map((s) => <option key={s.id} value={s.id}>{s.displayName}</option>)}
      </select>)}
      {field("Compare with", <select className={SELECT} value={vs} onChange={(e) => set("vs", e.target.value)}>
        <option value="city">City average</option>
        {sorted.filter((s) => s.id !== street).map((s) => <option key={s.id} value={s.id}>{s.displayName}</option>)}
      </select>)}
      {field("Period", <select className={SELECT} value={window} onChange={(e) => set("window", e.target.value)}>
        {(Object.keys(WINDOW_LABEL) as AnalysisWindow[]).map((w) => <option key={w} value={w}>{WINDOW_LABEL[w]}</option>)}
      </select>)}
      {field("Road users", <select className={SELECT} value={cls ?? ""} onChange={(e) => set("class", e.target.value)}>
        <option value="">All road users</option>
        {ROAD_USER_CLASSES.map((c) => <option key={c} value={c}>{classLabel(c)}</option>)}
      </select>)}
    </div>
  );
}
