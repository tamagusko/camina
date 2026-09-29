"use client";
import { usePathname, useRouter } from "next/navigation";
import { WINDOW_LABEL, type AnalysisWindow } from "@/lib/analysis";
import { SPEED_LIMIT_OPTIONS, type SpeedFocus } from "@/lib/speed";
import { MOTOR_CLASSES, ROAD_USER_CLASSES, classLabel } from "@/lib/types";

interface Props {
  streets: { id: string; displayName: string }[];
  street: string;
  window: AnalysisWindow;
  focus: SpeedFocus;
  limit: number | null;
  /** The road's own limit (OpenStreetMap), the default. */
  roadLimit: number | null;
}

const SELECT = "h-11 w-full min-w-0 rounded-sm border border-[var(--line)] bg-[var(--surface)] px-3 text-sm text-[var(--ink-1)]";
const OTHER_CLASSES = ROAD_USER_CLASSES.filter((c) => !(MOTOR_CLASSES as readonly string[]).includes(c));

/** Four selects; each change is a new URL, so every view can be shared. */
export function SpeedControls({ streets, street, window, focus, limit, roadLimit }: Props) {
  const router = useRouter();
  const pathname = usePathname();
  const set = (key: "street" | "window" | "class" | "limit", value: string) => {
    const chosen = { street, window, class: focus as string, limit: limit === null ? "" : String(limit), [key]: value };
    // A new road starts from its own limit.
    if (key === "street") chosen.limit = "";
    // Defaults stay out of the URL: all motor vehicles, the road's own limit.
    const next = new URLSearchParams({ street: chosen.street, window: chosen.window });
    if (chosen.class !== "motor") next.set("class", chosen.class);
    if (chosen.limit && Number(chosen.limit) !== roadLimit) next.set("limit", chosen.limit);
    router.replace(`${pathname}?${next.toString()}` as never, { scroll: false });
  };
  const sorted = [...streets].sort((a, b) => a.displayName.localeCompare(b.displayName));
  const limits = [...new Set([...(roadLimit !== null ? [roadLimit] : []), ...SPEED_LIMIT_OPTIONS])].sort((a, b) => a - b);
  const field = (label: string, control: React.ReactNode) => (
    <label className="flex min-w-0 flex-col gap-1 text-xs text-[var(--ink-2)]">{label}{control}</label>
  );
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4 print:hidden">
      {field("Road", <select className={SELECT} value={street} onChange={(e) => set("street", e.target.value)}>
        {sorted.map((s) => <option key={s.id} value={s.id}>{s.displayName}</option>)}
      </select>)}
      {field("Period", <select className={SELECT} value={window} onChange={(e) => set("window", e.target.value)}>
        {(Object.keys(WINDOW_LABEL) as AnalysisWindow[]).map((w) => <option key={w} value={w}>{WINDOW_LABEL[w]}</option>)}
      </select>)}
      {field("Road users", <select className={SELECT} value={focus} onChange={(e) => set("class", e.target.value)}>
        <option value="motor">All motor vehicles</option>
        {MOTOR_CLASSES.map((c) => <option key={c} value={c}>{classLabel(c)}</option>)}
        <optgroup label="Not bound by the road's limit">
          {OTHER_CLASSES.map((c) => <option key={c} value={c}>{classLabel(c)}</option>)}
        </optgroup>
      </select>)}
      {field("Speed limit", <select className={SELECT} value={limit ?? ""} onChange={(e) => set("limit", e.target.value)}>
        {roadLimit === null && <option value="">Not known</option>}
        {limits.map((l) => <option key={l} value={l}>{l === roadLimit ? `${l} km/h · OpenStreetMap` : `${l} km/h`}</option>)}
      </select>)}
    </div>
  );
}
