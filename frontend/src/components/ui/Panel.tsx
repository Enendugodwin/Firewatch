import clsx from "clsx";
import type { ReactNode } from "react";

export function Panel({
  title,
  subtitle,
  actions,
  children,
  className,
  bodyClassName,
  as: Tag = "section",
}: {
  title?: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  children?: ReactNode;
  className?: string;
  bodyClassName?: string;
  as?: "section" | "div" | "article";
}) {
  return (
    <Tag className={clsx("panel overflow-hidden", className)}>
      {title || actions ? (
        <header className="flex items-start justify-between gap-4 border-b border-line/70 px-4 py-3">
          <div className="min-w-0">
            {title ? (
              <h2 className="truncate text-sm font-semibold text-ink">{title}</h2>
            ) : null}
            {subtitle ? (
              <p className="mt-0.5 text-xs leading-relaxed text-muted">{subtitle}</p>
            ) : null}
          </div>
          {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
        </header>
      ) : null}
      <div className={clsx("px-4 py-3", bodyClassName)}>{children}</div>
    </Tag>
  );
}

export function StatTile({
  label,
  value,
  hint,
  tone = "neutral",
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  tone?: "neutral" | "warn" | "ok" | "info";
}) {
  const valueTone =
    tone === "warn"
      ? "text-warn"
      : tone === "ok"
        ? "text-ok"
        : tone === "info"
          ? "text-geo"
          : "text-ink";

  return (
    <div className="rounded-md border border-line/70 bg-raised/35 px-3 py-2.5">
      <div className="label">{label}</div>
      <div className={clsx("mt-1 font-mono text-lg font-medium leading-tight", valueTone)}>
        {value}
      </div>
      {hint ? <div className="mt-1 text-2xs leading-snug text-faint">{hint}</div> : null}
    </div>
  );
}
