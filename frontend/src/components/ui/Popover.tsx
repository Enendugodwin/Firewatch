import clsx from "clsx";
import { useEffect, useId, useRef, useState } from "react";
import type { ReactNode } from "react";

/**
 * Minimal accessible popover: click-outside and Escape to dismiss, focus stays
 * with the trigger. Not a full menu primitive — just enough for the header
 * controls, with no extra dependency.
 */
export function Popover({
  trigger,
  children,
  align = "right",
  widthClass = "w-72",
  label,
}: {
  trigger: (state: { open: boolean; toggle: () => void; id: string }) => ReactNode;
  children: (close: () => void) => ReactNode;
  align?: "left" | "right";
  widthClass?: string;
  label?: string;
}) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const id = useId();

  useEffect(() => {
    if (!open) return;

    function onPointerDown(event: MouseEvent | TouchEvent) {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false);
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }

    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("touchstart", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("touchstart", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  return (
    <div className="relative" ref={containerRef}>
      {trigger({ open, toggle: () => setOpen((value) => !value), id })}
      {open ? (
        <div
          id={id}
          aria-label={label}
          className={clsx(
            "absolute top-[calc(100%+0.5rem)] z-50 animate-fade-in rounded-panel border border-line bg-panel shadow-pop",
            widthClass,
            align === "right" ? "right-0" : "left-0",
          )}
        >
          {children(() => setOpen(false))}
        </div>
      ) : null}
    </div>
  );
}
