import { ROAD_USER_CLASSES, type RoadUserClass } from "@/lib/types";

// Okabe–Ito (colour-blind safe), one colour per class in wire order.
const SERIES_COLOURS = [
  "#e69f00",
  "#56b4e9",
  "#009e73",
  "#f0e442",
  "#0072b2",
  "#d55e00",
  "#cc79a7",
  "#999999",
  "var(--ink-1)",
];

export const CLASS_COLOURS = Object.fromEntries(
  ROAD_USER_CLASSES.map((cls, i) => [cls, SERIES_COLOURS[i]!]),
) as Record<RoadUserClass, string>;

export const TOOLTIP_STYLE = {
  contentStyle: {
    background: "var(--surface)",
    borderRadius: 6,
    border: "1px solid var(--line)",
    color: "var(--ink-1)",
    fontSize: 12,
  },
  labelStyle: { color: "var(--ink-1)" },
  itemStyle: { color: "var(--ink-1)" },
};
