import clsx from "clsx";
import type { ReactNode } from "react";

export type Tone = "neutral" | "info" | "ok" | "warn" | "danger" | "fire";

const TONE_CLASSES: Record<Tone, string> = {
  neutral: "border-line/12 text-muted",
  info: "border-azure/25 text-azure",
  ok: "border-accent/25 text-accent",
  warn: "border-warn/25 text-warn",
  danger: "border-danger/25 text-danger",
  fire: "border-fire-medium/25 text-fire-medium",
};

/**
 * Status pill. Labels are 10–11px uppercase with wide tracking, which is where
 * the system spends its emphasis instead of colour fills.
 */
export function Badge({
  children,
  tone = "neutral",
  className,
  title,
}: {
  children: ReactNode;
  tone?: Tone;
  className?: string;
  title?: string;
}) {
  return (
    <span
      title={title}
      className={clsx(
        "inline-flex items-center gap-1.5 rounded-full border px-2 py-[3px] text-3xs font-medium uppercase tracking-[0.14em]",
        TONE_CLASSES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
