import clsx from "clsx";

/**
 * Loading cues.
 *
 * The UI never shows an empty panel while a request is in flight: a spinner with
 * a plain-language label says what is being computed, and skeletons hold the
 * space the result will occupy. `role="status"` + `aria-live="polite"` announce
 * the state to assistive technology without interrupting the user, and every
 * animation is disabled under `prefers-reduced-motion`.
 */
export function LoadingCue({
  label = "Loading…",
  className,
}: {
  label?: string;
  className?: string;
}) {
  return (
    <div
      role="status"
      aria-live="polite"
      className={clsx(
        "inline-flex items-center gap-2 text-2xs font-light text-muted",
        className,
      )}
    >
      <span
        aria-hidden
        className="size-3.5 shrink-0 animate-spin rounded-full border border-line/25 border-t-accent motion-reduce:animate-none"
      />
      <span>{label}</span>
    </div>
  );
}

export function SkeletonLine({ className }: { className?: string }) {
  return (
    <div
      aria-hidden
      className={clsx(
        "h-3 animate-pulse rounded-full bg-line/[0.07] motion-reduce:animate-none",
        className,
      )}
    />
  );
}

/** A cue plus placeholder lines, for a panel whose content is not ready. */
export function LoadingBlock({
  label,
  lines = 3,
  className,
}: {
  label?: string;
  lines?: number;
  className?: string;
}) {
  return (
    <div className={clsx("space-y-3", className)}>
      <LoadingCue label={label} />
      <div className="space-y-2" aria-hidden>
        {Array.from({ length: lines }).map((_, index) => (
          <SkeletonLine
            key={index}
            className={index === lines - 1 ? "w-2/3" : "w-full"}
          />
        ))}
      </div>
    </div>
  );
}
