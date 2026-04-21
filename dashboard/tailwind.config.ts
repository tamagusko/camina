import type { Config } from "tailwindcss";

// Tokens from DESIGN.md (Uber-inspired).
const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Brand
        black: "#000000",
        white: "#ffffff",
        // Interactive greys
        "hover-gray": "#e2e2e2",
        "hover-light": "#f3f3f3",
        "chip-gray": "#efefef",
        // Text
        "body-gray": "#4b4b4b",
        "muted-gray": "#afafaf",
        // Link states
        "link-blue": "#0000ee",
      },
      fontFamily: {
        display: [
          "UberMove",
          "UberMoveText",
          "system-ui",
          "Helvetica Neue",
          "Helvetica",
          "Arial",
          "sans-serif",
        ],
        body: [
          "UberMoveText",
          "system-ui",
          "Helvetica Neue",
          "Helvetica",
          "Arial",
          "sans-serif",
        ],
      },
      fontSize: {
        display: ["3.25rem", { lineHeight: "1.23", fontWeight: "700" }],
        section: ["2.25rem", { lineHeight: "1.22", fontWeight: "700" }],
        card: ["2rem", { lineHeight: "1.25", fontWeight: "700" }],
        sub: ["1.5rem", { lineHeight: "1.33", fontWeight: "700" }],
        small: ["1.25rem", { lineHeight: "1.4", fontWeight: "700" }],
        nav: ["1.125rem", { lineHeight: "1.33", fontWeight: "500" }],
        body: ["1rem", { lineHeight: "1.5", fontWeight: "400" }],
        caption: ["0.875rem", { lineHeight: "1.43", fontWeight: "400" }],
        micro: ["0.75rem", { lineHeight: "1.67", fontWeight: "400" }],
      },
      borderRadius: {
        pill: "999px",
        card: "8px",
        feature: "12px",
      },
      boxShadow: {
        subtle: "rgba(0,0,0,0.12) 0px 4px 16px",
        medium: "rgba(0,0,0,0.16) 0px 4px 16px",
        float: "rgba(0,0,0,0.16) 0px 2px 8px",
      },
      spacing: {
        "1.5": "6px",
        "2.5": "10px",
        "3.5": "14px",
        "4.5": "18px",
      },
    },
  },
  plugins: [],
};

export default config;
