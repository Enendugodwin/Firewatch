import { CalendarRange, Check } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Popover } from "@/components/ui/Popover";
import { RANGE_PRESETS, useUiStore } from "@/store/ui";
import type { RangePreset } from "@/store/ui";

export function DateRangeControl() {
  const dateRange = useUiStore((state) => state.dateRange);
  const setPreset = useUiStore((state) => state.setPreset);
  const setCustomRange = useUiStore((state) => state.setCustomRange);

  const presetLabel =
    RANGE_PRESETS.find((preset) => preset.value === dateRange.preset)?.label ?? "Custom range";

  return (
    <Popover
      label="Observation period"
      widthClass="w-80"
      trigger={({ open, toggle, id }) => (
        <button
          type="button"
          id={id}
          onClick={toggle}
          aria-expanded={open}
          aria-haspopup="dialog"
          className="inline-flex h-8 items-center gap-2 rounded-md border border-line bg-raised/50 px-2.5 text-xs text-muted transition-colors hover:text-ink"
        >
          <CalendarRange className="size-3.5 text-faint" aria-hidden />
          <span className="hidden font-mono text-2xs sm:inline">{dateRange.start}</span>
          <span className="hidden text-faint sm:inline">→</span>
          <span className="hidden font-mono text-2xs sm:inline">{dateRange.end}</span>
          <span className="sm:hidden">Period</span>
        </button>
      )}
    >
      {() => (
        <div className="p-3">
          <div className="label mb-2">Observation period (UTC)</div>
          <ul className="space-y-1">
            {RANGE_PRESETS.map((preset) => (
              <li key={preset.value}>
                <button
                  type="button"
                  onClick={() => setPreset(preset.value)}
                  className={`flex w-full items-center justify-between rounded px-2 py-1.5 text-xs ${
                    dateRange.preset === preset.value
                      ? "bg-raised text-ink"
                      : "text-muted hover:bg-raised/60 hover:text-ink"
                  }`}
                >
                  {preset.label}
                  {dateRange.preset === preset.value ? (
                    <Check className="size-3.5 text-fire-medium" aria-hidden />
                  ) : null}
                </button>
              </li>
            ))}
          </ul>

          <div className="mt-3 border-t border-line/70 pt-3">
            <div className="label mb-2">Custom range</div>
            <div className="grid grid-cols-2 gap-2">
              <label className="text-2xs text-faint">
                Start
                <input
                  type="date"
                  value={dateRange.start}
                  max={dateRange.end}
                  onChange={(event) => setCustomRange(event.target.value, dateRange.end)}
                  className="mt-1 w-full rounded border border-line bg-canvas px-2 py-1.5 font-mono text-2xs text-ink"
                />
              </label>
              <label className="text-2xs text-faint">
                End
                <input
                  type="date"
                  value={dateRange.end}
                  min={dateRange.start}
                  onChange={(event) => setCustomRange(dateRange.start, event.target.value)}
                  className="mt-1 w-full rounded border border-line bg-canvas px-2 py-1.5 font-mono text-2xs text-ink"
                />
              </label>
            </div>
            <p className="mt-2 text-2xs leading-relaxed text-faint">
              The selected period ({presetLabel.toLowerCase()}) is shared by every module and will
              drive queries once observations exist.
            </p>
            <Button
              size="sm"
              variant="ghost"
              className="mt-2 w-full"
              onClick={() => setPreset("7d")}
            >
              Reset to last 7 days
            </Button>
          </div>
        </div>
      )}
    </Popover>
  );
}

/** Read the active range in a typed way for pages and the status bar. */
export function useActiveRange() {
  const range = useUiStore((state) => state.dateRange);
  return range;
}

export type { RangePreset };
