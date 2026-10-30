import type { Config } from "tailwindcss";

/**
 * FIREWATCH X design system.
 *
 * Visual language: "Orbital Intelligence" — near-black canvas, deep navy glass
 * surfaces, hairline white borders with a gradient edge shell, Newsreader
 * display type against light-weight Inter, and a restrained green accent.
 * Motion is minimal; data density is preserved without visual noise.
 *
 * Fire severity colours are semantic data colours (amber/orange/red) and are
 * deliberately separate from the interaction accent (green).
 */
const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "rgb(var(--fw-bg) / <alpha-value>)",
        panel: "rgb(var(--fw-surface) / <alpha-value>)",
        raised: "rgb(var(--fw-raised) / <alpha-value>)",
        ink: "rgb(var(--fw-ink) / <alpha-value>)",
        muted: "rgb(var(--fw-muted) / <alpha-value>)",
        faint: "rgb(var(--fw-faint) / <alpha-value>)",
        line: "rgb(var(--fw-line) / <alpha-value>)",
        accent: "rgb(var(--fw-accent) / <alpha-value>)",
        azure: "rgb(var(--fw-azure) / <alpha-value>)",
        cyan: "rgb(var(--fw-cyan) / <alpha-value>)",
        // Semantic fire-activity scale (data only, never chrome).
        fire: {
          low: "#FACC15",
          medium: "#FB923C",
          high: "#EF4444",
        },
        ok: "#60D58B",
        warn: "#FACC15",
        danger: "#F87171",
      },
      fontFamily: {
        display: ["Newsreader Variable", "Newsreader", "Georgia", "serif"],
        sans: ["Inter Variable", "Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      fontSize: {
        display: ["2.75rem", { lineHeight: "1.05", letterSpacing: "-0.025em" }],
        "2xs": ["0.6875rem", { lineHeight: "1rem", letterSpacing: "0.02em" }],
        "3xs": ["0.625rem", { lineHeight: "0.875rem", letterSpacing: "0.06em" }],
      },
      borderRadius: {
        control: "8px",
        tag: "7px",
        card: "11px",
        shell: "12px",
      },
      boxShadow: {
        glass: "0 0 24px 0 rgb(255 255 255 / 0.06), inset 0 1px 0 0 rgb(255 255 255 / 0.05)",
        halo: "0 0 18px 0 rgb(96 213 139 / 0.18)",
        azure: "0 0 8px 0 rgb(59 130 246 / 0.45)",
        lift: "0 24px 60px -32px rgb(0 0 0 / 0.9), 0 0 0 1px rgb(255 255 255 / 0.06)",
      },
      backdropBlur: {
        glass: "14px",
      },
      keyframes: {
        "fade-up": {
          from: { opacity: "0", transform: "translateY(4px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        breathe: {
          "0%, 100%": { opacity: "0.55" },
          "50%": { opacity: "1" },
        },
        orbit: {
          from: { transform: "rotate(0deg)" },
          to: { transform: "rotate(360deg)" },
        },
      },
      animation: {
        "fade-up": "fade-up 240ms cubic-bezier(0.2, 1, 0.4, 1) both",
        breathe: "breathe 4s ease-in-out infinite",
        orbit: "orbit 90s linear infinite",
      },
      transitionTimingFunction: {
        orbital: "cubic-bezier(0.2, 1, 0.4, 1)",
      },
    },
  },
  plugins: [],
};

export default config;
