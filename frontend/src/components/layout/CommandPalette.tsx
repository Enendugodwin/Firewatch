import { CornerDownLeft, Search, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { NAV_ITEMS } from "@/config/nav";
import { useUiStore } from "@/store/ui";

/** Keyboard-first jump-to-module palette (Ctrl/⌘ + K, or "/"). */
export function CommandPalette() {
  const open = useUiStore((state) => state.commandOpen);
  const setOpen = useUiStore((state) => state.setCommandOpen);
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const results = useMemo(() => {
    const term = query.trim().toLowerCase();
    if (!term) return NAV_ITEMS;
    return NAV_ITEMS.filter(
      (item) =>
        item.label.toLowerCase().includes(term) ||
        item.group.toLowerCase().includes(term) ||
        item.key.includes(term),
    );
  }, [query]);

  useEffect(() => {
    if (!open) return;
    setQuery("");
    setActiveIndex(0);
    const frame = requestAnimationFrame(() => inputRef.current?.focus());
    return () => cancelAnimationFrame(frame);
  }, [open]);

  useEffect(() => {
    setActiveIndex(0);
  }, [query]);

  if (!open) return null;

  function go(to: string) {
    setOpen(false);
    navigate(to);
  }

  function onKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((index) => Math.min(index + 1, results.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((index) => Math.max(index - 1, 0));
    } else if (event.key === "Enter") {
      event.preventDefault();
      const target = results[activeIndex];
      if (target) go(target.to);
    } else if (event.key === "Escape") {
      event.preventDefault();
      setOpen(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-[80] flex items-start justify-center bg-black/70 px-4 pt-[14vh] backdrop-blur-sm"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) setOpen(false);
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Jump to a module"
        className="w-full max-w-xl animate-fade-up rounded-shell p-px shadow-lift"
        style={{
          backgroundImage:
            "linear-gradient(to bottom right, rgb(255 255 255 / 0.18), rgb(255 255 255 / 0.04), transparent)",
        }}
      >
        <div className="overflow-hidden rounded-card border border-line/[0.06] bg-panel">
          <div className="flex items-center gap-[10px] border-b border-line/[0.07] px-4 py-[13px]">
            <Search className="size-4 shrink-0 text-faint" aria-hidden />
            <input
              ref={inputRef}
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={onKeyDown}
              placeholder="Jump to a module — try “calendar” or “anomaly”"
              aria-label="Search modules"
              aria-activedescendant={
                results[activeIndex] ? `cmd-${results[activeIndex].key}` : undefined
              }
              className="w-full bg-transparent text-[13px] font-light text-ink placeholder:text-faint focus:outline-none focus-visible:ring-0"
            />
            <button
              type="button"
              onClick={() => setOpen(false)}
              aria-label="Close search"
              className="rounded-full p-1 text-faint transition-colors duration-150 hover:bg-line/[0.06] hover:text-ink"
            >
              <X className="size-3.5" aria-hidden />
            </button>
          </div>

          <ul role="listbox" className="max-h-[24rem] overflow-y-auto p-[6px]">
            {results.length === 0 ? (
              <li className="px-3 py-8 text-center text-xs font-light text-faint">
                No module matches “{query}”.
              </li>
            ) : (
              results.map((item, index) => {
                const Icon = item.icon;
                const active = index === activeIndex;
                return (
                  <li
                    key={item.key}
                    id={`cmd-${item.key}`}
                    role="option"
                    aria-selected={active}
                    onMouseEnter={() => setActiveIndex(index)}
                    onMouseDown={(event) => {
                      event.preventDefault();
                      go(item.to);
                    }}
                    className={`flex cursor-pointer items-center gap-[10px] rounded-control px-[10px] py-[9px] text-[13px] font-light transition-colors duration-150 ${
                      active ? "bg-line/[0.06] text-ink" : "text-muted"
                    }`}
                  >
                    <Icon
                      className={`size-[15px] shrink-0 ${active ? "text-accent" : "text-faint"}`}
                      aria-hidden
                    />
                    <span className="flex-1 truncate">{item.label}</span>
                    <span className="hidden text-2xs text-faint sm:inline">{item.group}</span>
                    {active ? (
                      <CornerDownLeft className="size-3 shrink-0 text-faint" aria-hidden />
                    ) : null}
                  </li>
                );
              })
            )}
          </ul>
        </div>
      </div>
    </div>
  );
}
