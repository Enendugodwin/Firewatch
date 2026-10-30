import clsx from "clsx";
import type { ReactNode } from "react";

import type { Tone } from "./Badge";

const DOT_CLASSES: Record<Tone, string> = {
  neutral: "bg-faint",
  info: "bg-geo",
  ok: "bg-ok",
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
        "inline-block size-1.5 shrink-0 rounded-full",
        DOT_CLASSES[tone],
        pulse && "animate-pulse-ring",
        className,
      )}
    />
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
