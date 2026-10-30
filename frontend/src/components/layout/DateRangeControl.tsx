import { CalendarRange, Check } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Popover } from "@/components/ui/Popover";
import { RANGE_PRESETS, useUiStore } from "@/store/ui";
import type { RangePreset } from "@/store/ui";

const trigger =
  "inline-flex h-8 items-center gap-2 rounded-full border border-line/10 bg-line/[0.03] px-[10px] text-2xs font-light text-muted transition-colors duration-150 hover:border-line/20 hover:text-ink";

export function DateRangeControl() {
  const dateRange = useUiStore((state) => state.dateRange);
  const setPreset = useUiStore((state) => state.setPreset);
  const setCustomRange = useUiStore((state) => state.setCustomRange);

  const presetLabel =
    RANGE_PRESETS.find((preset) => preset.value === dateRange.preset)?.label ?? "Custom range";

  return (
    <Popover
      label="Observation period"
      widthClass="w-[19rem]"
      trigger={({ open, toggle, id }) => (
        <button
          type="button"
          id={id}
          onClick={toggle}
          aria-expanded={open}
          aria-haspopup="dialog"
          className={trigger}
        >
          <CalendarRange className="size-3.5 text-faint" aria-hidden />
          <span className="hidden font-mono text-3xs sm:inline">{dateRange.start}</span>
          <span className="hidden text-line/30 sm:inline">→</span>
          <span className="hidden font-mono text-3xs sm:inline">{dateRange.end}</span>
          <span className="sm:hidden">Period</span>
        </button>
      )}
    >
      {() => (
        <div className="p-[14px]">
          <div className="label mb-[10px]">Observation period (UTC)</div>
          <ul className="space-y-[1px]">
            {RANGE_PRESETS.map((preset) => (
              <li key={preset.value}>
                <button
                  type="button"
                  onClick={() => setPreset(preset.value)}
                  className={`flex w-full items-center justify-between rounded-control px-[10px] py-[7px] text-xs font-light transition-colors duration-150 ${
                    dateRange.preset === preset.value
                      ? "bg-line/[0.06] text-ink"
                      : "text-muted hover:bg-line/[0.04] hover:text-ink"
                  }`}
                >
                  {preset.label}
                  {dateRange.preset === preset.value ? (
                    <Check className="size-3.5 text-accent" aria-hidden />
                  ) : null}
                </button>
              </li>
            ))}
          </ul>

          <div className="mt-[14px] border-t border-line/[0.07] pt-[12px]">
            <div className="label mb-[8px]">Custom range</div>
            <div className="grid grid-cols-2 gap-[8px]">
              <label className="text-2xs font-light text-faint">
                Start
                <input
                  type="date"
                  value={dateRange.start}
                  max={dateRange.end}
                  onChange={(event) => setCustomRange(event.target.value, dateRange.end)}
                  className="mt-[5px] w-full rounded-control border border-line/10 bg-canvas/60 px-2 py-1.5 font-mono text-3xs text-ink"
                />
              </label>
              <label className="text-2xs font-light text-faint">
                End
                <input
                  type="date"
                  value={dateRange.end}
                  min={dateRange.start}
                  onChange={(event) => setCustomRange(dateRange.start, event.target.value)}
                  className="mt-[5px] w-full rounded-control border border-line/10 bg-canvas/60 px-2 py-1.5 font-mono text-3xs text-ink"
                />
              </label>
            </div>
            <p className="mt-2 text-2xs font-light leading-relaxed text-faint">
              The selected period ({presetLabel.toLowerCase()}) is shared by every module and will
              drive queries once observations exist.
            </p>
            <Button
              size="sm"
              variant="ghost"
              className="mt-[6px] w-full"
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

export type { RangePreset };
