import clsx from "clsx";
import type { ReactNode } from "react";

import type { Tone } from "./Badge";

const DOT_CLASSES: Record<Tone, string> = {
  neutral: "bg-line/30",
  info: "bg-azure",
  ok: "bg-accent",
  warn: "bg-warn",
  danger: "bg-danger",
  fire: "bg-fire-medium",
};

export function StatusDot({
  tone = "neutral",
  pulse = false,
  className,
  label,
}: {
  tone?: Tone;
  pulse?: boolean;
  className?: string;
  label?: string;
}) {
  return (
    <span
      role={label ? "img" : undefined}
      aria-label={label}
      className={clsx(
        "relative inline-block size-[5px] shrink-0 rounded-full",
        DOT_CLASSES[tone],
        className,
      )}
    >
      {pulse ? (
        <span
          aria-hidden
          className={clsx("absolute inset-0 animate-breathe rounded-full", DOT_CLASSES[tone])}
        />
      ) : null}
    </span>
  );
}

export function StatusLine({
  tone = "neutral",
  children,
  pulse = false,
}: {
  tone?: Tone;
  children: ReactNode;
  pulse?: boolean;
}) {
  return (
    <span className="inline-flex items-center gap-2 text-xs text-muted">
      <StatusDot tone={tone} pulse={pulse} />
      {children}
    </span>
  );
}
