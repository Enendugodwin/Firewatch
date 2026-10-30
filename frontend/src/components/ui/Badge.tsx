import clsx from "clsx";
import type { ReactNode } from "react";

export type Tone = "neutral" | "info" | "ok" | "warn" | "danger" | "fire";

const TONE_CLASSES: Record<Tone, string> = {
  neutral: "border-line text-muted bg-raised/60",
  info: "border-geo/30 text-geo bg-geo/10",
  ok: "border-ok/30 text-ok bg-ok/10",
  warn: "border-warn/30 text-warn bg-warn/10",
  danger: "border-danger/30 text-danger bg-danger/10",
  fire: "border-fire-medium/40 text-fire-medium bg-fire-medium/10",
};

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
        "inline-flex items-center gap-1.5 rounded border px-1.5 py-0.5 text-3xs font-medium uppercase tracking-[0.1em]",
        TONE_CLASSES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
