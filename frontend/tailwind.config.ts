import type { Config } from "tailwindcss";

/**
 * FIREWATCH X design tokens.
 *
 * The palette is fixed by the product specification (§9.1): deep navy and
 * charcoal surfaces, amber/orange/red reserved for fire activity, cyan for
 * geography, green for healthy system state. Surfaces are driven by CSS
 * variables so the high-contrast theme can re-map them without touching
 * component code.
 */
const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "rgb(var(--fw-canvas) / <alpha-value>)",
        sidebar: "rgb(var(--fw-sidebar) / <alpha-value>)",
        panel: "rgb(var(--fw-panel) / <alpha-value>)",
        raised: "rgb(var(--fw-raised) / <alpha-value>)",
        line: "rgb(var(--fw-line) / <alpha-value>)",
        ink: "rgb(var(--fw-ink) / <alpha-value>)",
        muted: "rgb(var(--fw-muted) / <alpha-value>)",
        faint: "rgb(var(--fw-faint) / <alpha-value>)",
        fire: {
          low: "#FACC15",
          medium: "#FB923C",
          high: "#EF4444",
        },
        geo: "#38BDF8",
        ok: "#22C55E",
        warn: "#FACC15",
        danger: "#EF4444",
      },
      fontFamily: {
        sans: ["Inter Variable", "Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      fontSize: {
        "2xs": ["0.6875rem", { lineHeight: "1rem", letterSpacing: "0.04em" }],
        "3xs": ["0.625rem", { lineHeight: "0.875rem", letterSpacing: "0.06em" }],
      },
      boxShadow: {
        panel: "0 1px 0 0 rgb(var(--fw-line) / 0.6), 0 8px 24px -18px rgb(0 0 0 / 0.9)",
        pop: "0 18px 48px -20px rgb(0 0 0 / 0.9), 0 0 0 1px rgb(var(--fw-line))",
      },
      borderRadius: {
        panel: "0.5rem",
      },
      keyframes: {
        "fade-in": {
          from: { opacity: "0", transform: "translateY(2px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        pulseRing: {
          "0%": { boxShadow: "0 0 0 0 rgb(34 197 94 / 0.45)" },
          "70%": { boxShadow: "0 0 0 6px rgb(34 197 94 / 0)" },
          "100%": { boxShadow: "0 0 0 0 rgb(34 197 94 / 0)" },
        },
      },
      animation: {
        "fade-in": "fade-in 160ms ease-out",
        "pulse-ring": "pulseRing 2.4s ease-out infinite",
      },
    },
  },
  plugins: [],
};

export default config;
