// Regression: the desktop panel rendered one viewport-height below the screen.
// `cn()` runs tailwind-merge, and a trailing `md:inset-auto` made it drop the
// earlier `md:right-0 md:top-0`, leaving a fixed element with every inset auto
// — i.e. at its static position, under the full-height map. Clicking a street
// "did nothing" because the panel opened where nobody could see it.
import { describe, expect, it } from "vitest";

import { PANEL_CLASS } from "@/components/panels/StreetSidePanel";

const classes = () => PANEL_CLASS.split(/\s+/);

describe("StreetSidePanel placement classes", () => {
  it("keeps the desktop anchors after tailwind-merge", () => {
    expect(classes()).toEqual(expect.arrayContaining(["md:right-0", "md:top-0"]));
  });

  it("keeps the mobile bottom-sheet anchors after tailwind-merge", () => {
    expect(classes()).toEqual(expect.arrayContaining(["inset-x-0", "bottom-0"]));
  });
});
